import os
import datetime
import tempfile
import requests
from google import genai
from google.genai import types
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

# 설정 정보
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_BLOG_DATABASE_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

# API 초기화
gemini_client = genai.Client(api_key=GEMINI_API_KEY)
notion = Client(auth=NOTION_TOKEN)


def send_telegram_report(title, success=True):
    message = f"✅ [학원 블로그 자동화 완료]\n주제: {title}" if success else "❌ [자동화 실패] 오류 발생"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": message})


def generate_and_upload_image(topic):
    """주제에 맞는 이미지 생성 후 catbox.moe에 업로드하여 URL 반환"""
    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=f"'{topic}' 주제의 교육 블로그에 어울리는 깔끔한 이미지를 생성해줘",
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            )
        )

        image_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image_data = part.inline_data.data
                break

        if not image_data:
            print("이미지 데이터 없음")
            return None

        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(image_data)
            tmp_path = f.name

        # catbox.moe에 업로드 (무료, 가입 불필요)
        with open(tmp_path, "rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": ("image.png", f, "image/png")}
            )
        os.remove(tmp_path)

        if resp.status_code == 200 and resp.text.startswith("https://"):
            print(f"이미지 업로드 완료: {resp.text.strip()}")
            return resp.text.strip()

        print(f"이미지 업로드 실패: {resp.text}")
        return None

    except Exception as e:
        print(f"이미지 생성/업로드 오류: {e}")
        return None


def blog_automation_job():
    try:
        # 1) 주제 선정 및 초안 작성
        topics = ["초등 영어 파닉스 전략", "중등 내신 만점 비결", "영어 원서 읽기"]
        selected_topic = topics[datetime.datetime.now().day % len(topics)]

        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=f"'{selected_topic}' 주제로 블로그 글 작성해줘."
        )

        # 2) 이미지 생성 및 업로드
        image_url = generate_and_upload_image(selected_topic)

        # 3) 노션 저장
        properties = {
            "제목": {"title": [{"text": {"content": selected_topic}}]},
            "날짜": {"date": {"start": datetime.date.today().isoformat()}},
            "본문": {"rich_text": [{"text": {"content": response.text[:1900]}}]},
        }
        if image_url:
            properties["이미지"] = {"files": [{"name": "blog_image.png", "external": {"url": image_url}}]}

        notion.pages.create(
            parent={"database_id": DATABASE_ID},
            properties=properties
        )

        send_telegram_report(selected_topic, True)
        print(f"완료: {selected_topic}")

    except Exception as e:
        print(f"Error: {e}")
        send_telegram_report("", False)


if __name__ == "__main__":
    blog_automation_job()
