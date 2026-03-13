import os
import re
import json
import whisper
from google import genai
from notion_client import Client as NotionClient
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# 1. 환경 설정 로드
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_CS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# 2. 클라이언트 초기화
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
notion = NotionClient(auth=NOTION_TOKEN)

# 3. Whisper 모델 로드
print("Whisper 모델을 로드 중입니다...")
whisper_model = whisper.load_model("base")


def parse_filename_info(filename):
    """파일명에서 통화일시와 전화번호를 추출
    형식: 01012345678_260311_150422.m4a
    """
    date_time = "정보 없음"
    phone = "정보 없음"

    if not filename:
        return date_time, phone

    print(f"--- 분석 중인 파일명: {filename} ---")

    match = re.search(r'(\d{9,13})_(\d{6})_(\d{6})', filename)
    if match:
        raw_phone, raw_date, raw_time = match.groups()

        phone = raw_phone
        if phone.startswith('82'):
            phone = '0' + phone[2:]

        yy, mo, d = raw_date[:2], raw_date[2:4], raw_date[4:6]
        h, mi = raw_time[:2], raw_time[2:4]
        date_time = f"20{yy}년 {mo}월 {d}일 {h}:{mi}"

    return date_time, phone


async def analyze_with_gemini(text):
    """제미나이를 사용하여 정보를 추출하는 함수"""
    prompt = f"""
    당신은 입시 학원의 상담 전문 비서입니다.
    다음 상담 녹취록을 읽고 아래 항목을 추출하여 'JSON 형식'으로만 응답하세요.
    항목을 찾을 수 없으면 "정보 없음"이라고 기재하세요.

    반드시 아래의 키 이름을 그대로 사용하세요 (번호 없이):
    "이름", "성별", "진행도", "학교", "학년", "학생 연락처",
    "수업 가능 일시", "현재 성적", "목표", "참고사항", "주요 통화 내용"

    상담 내용:
    {text}
    """
    response = gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    result_text = response.text.replace('```json', '').replace('```', '').strip()
    print(f"--- Gemini 응답 ---\n{result_text}\n-------------------")
    return result_text


def _parse_notion_date(date_str):
    """'2026년 03월 11일 15:04' 형식을 Notion date 형식으로 변환"""
    m = re.match(r'(\d{4})년 (\d{2})월 (\d{2})일 (\d{2}):(\d{2})', date_str or "")
    if m:
        y, mo, d, h, mi = m.groups()
        return f"{y}-{mo}-{d}T{h}:{mi}:00+09:00"
    return None


async def save_to_notion(data):
    """추출된 JSON 데이터를 노션 데이터베이스에 저장하는 함수"""
    def val(key):
        return data.get(key, "정보 없음")

    def phone(key):
        v = val(key)
        return v if v != "정보 없음" else None

    try:
        notion_date = _parse_notion_date(val("상담일시"))

        properties = {
            "이름":         {"title": [{"text": {"content": val("이름")}}]},
            "성별":         {"select": {"name": val("성별")}},
            "학교":         {"multi_select": [{"name": val("학교")}]},
            "학년":         {"email": val("학년")},
            "학생 연락처":  {"phone_number": phone("학생 연락처")},
            "학부모 연락처":{"phone_number": phone("학부모 연락처")},
            "수업 가능 일시":{"rich_text": [{"text": {"content": val("수업 가능 일시")}}]},
            "현재 성적":    {"rich_text": [{"text": {"content": val("현재 성적")}}]},
            "목표":         {"rich_text": [{"text": {"content": val("목표")}}]},
            "참고사항":     {"rich_text": [{"text": {"content": val("참고사항")}}]},
            "주요 통화 내용":{"rich_text": [{"text": {"content": val("주요 통화 내용")}}]},
        }
        if notion_date:
            properties["상담일시"] = {"date": {"start": notion_date}}

        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties
        )
        return True
    except Exception as e:
        print(f"노션 저장 중 오류 발생: {e}")
        return False


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """텔레그램 음성 메시지 처리 핸들러"""
    await update.message.reply_text("음성 파일을 받았습니다. 분석을 시작합니다 (1/2)...")

    # 파일 및 파일명 가져오기
    if update.message.voice:
        file_obj = update.message.voice
        filename = file_obj.file_unique_id
    else:
        file_obj = update.message.audio
        filename = update.message.audio.file_name or file_obj.file_unique_id

    # 파일명에서 상담일시·학부모 연락처 추출
    date_time, parent_phone = parse_filename_info(filename)

    file = await context.bot.get_file(file_obj.file_id)
    file_path = "temp_audio.ogg"
    await file.download_to_drive(file_path)

    try:
        # 단계 1: Whisper로 텍스트 변환
        result = whisper_model.transcribe(file_path)
        transcribed_text = result['text']

        await update.message.reply_text("텍스트 변환 완료! 제미나이가 분석 중입니다 (2/2)...")

        # 단계 2: Gemini로 정보 추출
        extracted_json_str = await analyze_with_gemini(transcribed_text)

        # 단계 3: 파일명 추출 항목 병합
        try:
            extracted = json.loads(extracted_json_str)
        except json.JSONDecodeError:
            extracted = {}

        final = {
            "상담일시": date_time,
            **extracted,
            "학부모 연락처": parent_phone,
        }
        final_str = json.dumps(final, ensure_ascii=False, indent=2)

        await update.message.reply_text(f"✅ 분석 완료!\n\n```json\n{final_str}\n```", parse_mode="Markdown")
        print(f"추출 데이터: {final_str}")

        # 단계 4: 노션에 저장
        success = await save_to_notion(final)
        if success:
            await update.message.reply_text("✅ 노션 데이터베이스에 성공적으로 기록되었습니다!")
        else:
            await update.message.reply_text("⚠️ 분석은 완료되었으나 노션 저장에 실패했습니다.")

    except Exception as e:
        await update.message.reply_text(f"❌ 오류 발생: {str(e)}")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


if __name__ == '__main__':
    print("상담 자동화 봇이 가동되었습니다.")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))

    app.run_polling()
