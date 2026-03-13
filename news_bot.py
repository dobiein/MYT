import os
import requests
from bs4 import BeautifulSoup
from google import genai
from dotenv import load_dotenv

load_dotenv()

# --- 설정 구간 ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SOURCES = {
    "베리타스알파": "http://www.veritas-a.com/news/articleList.html?sc_section_code=S1N1",
    "에듀진": "http://www.edujin.co.kr/news/articleList.html?sc_section_code=S1N2",
    "에듀동아": "http://edu.donga.com/?p=1&ps=news",
    "조선에듀": "https://edu.chosun.com"
}
# ----------------

# AI 설정
client = genai.Client(api_key=GEMINI_API_KEY)

AD_KEYWORDS = ["구독체험", "구독신청", "광고", "이벤트", "제휴", "홍보"]

def is_ad(text):
    return any(kw in text for kw in AD_KEYWORDS)

def get_news():
    """지정한 4개 사이트에서 입시 뉴스를 수집합니다."""
    headers = {"User-Agent": "Mozilla/5.0"}
    all_news = []

    # 1. 베리타스알파
    try:
        res = requests.get(SOURCES["베리타스알파"], headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        titles = [a for a in soup.select('a[href*="articleView"]') if a.get_text(strip=True) and not is_ad(a.get_text(strip=True))]
        for t in titles[:3]:
            href = t['href']
            if not href.startswith('http'):
                href = f"https://www.veritas-a.com{href}"
            all_news.append(f"[베리타스알파] {t.get_text(strip=True)} ({href})")
    except Exception as e:
        print(f"베리타스알파 수집 중 오류: {e}")

    # 2. 에듀진
    try:
        res = requests.get(SOURCES["에듀진"], headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        titles = [a for a in soup.select('a[href*="articleView"]') if a.get_text(strip=True) and not is_ad(a.get_text(strip=True))]
        for t in titles[:3]:
            href = t['href']
            if not href.startswith('http'):
                href = f"http://www.edujin.co.kr{href}"
            all_news.append(f"[에듀진] {t.get_text(strip=True)} ({href})")
    except Exception as e:
        print(f"에듀진 수집 중 오류: {e}")

    # 3. 에듀동아
    try:
        res = requests.get(SOURCES["에듀동아"], headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        titles = [a for a in soup.select('a[href*="articleView"]') if a.get_text(strip=True) and not is_ad(a.get_text(strip=True))]
        seen = set()
        count = 0
        for t in titles:
            href = t['href']
            if href not in seen:
                seen.add(href)
                all_news.append(f"[에듀동아] {t.get_text(strip=True)} ({href})")
                count += 1
                if count >= 3:
                    break
    except Exception as e:
        print(f"에듀동아 수집 중 오류: {e}")

    # 4. 조선에듀
    try:
        res = requests.get(SOURCES["조선에듀"], headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        titles = [a for a in soup.select('a[href*="html_dir"]') if a.get_text(strip=True) and len(a.get_text(strip=True)) > 10 and not is_ad(a.get_text(strip=True))]
        seen = set()
        count = 0
        for t in titles:
            href = t['href']
            if href not in seen:
                seen.add(href)
                all_news.append(f"[조선에듀] {t.get_text(strip=True)} ({href})")
                count += 1
                if count >= 3:
                    break
    except Exception as e:
        print(f"조선에듀 수집 중 오류: {e}")

    return "\n".join(all_news)

def summarize_with_ai(news_text):
    """AI를 사용하여 충청 지역 및 비학군지 뉴스를 우선적으로 요약합니다."""
    prompt = f"""
    너는 교육 전문 입시 컨설턴트야. 아래 뉴스 목록에서 다음 조건에 맞는 기사를 찾아 요약해줘.

    1. 핵심 키워드: 충남 지역(충남, 특히 서산, 당진, 아산, 천안), 비학군지 입시, 중고등 진학 정보.
    2. 요약 방식:
       - 충남청 지역 관련 소식이 있다면 최상단에 배치하고 '📍 [충남]' 태그를 붙여줘.
       - 그 외 중요한 비학군지 입시 정보는 '✅' 태그를 붙여줘.
       - 각 기사당 1~2줄로 핵심만 요약하고, 관련 링크를 포함해줘.

    내용: {news_text}
    """
    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
    return response.text

def send_telegram(message):
    """텔레그램 메시지 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': CHAT_ID, 'text': message})

if __name__ == "__main__":
    print("뉴스 요약 시작...")
    raw_news = get_news()
    summary = summarize_with_ai(raw_news)
    send_telegram(f"📅 오늘의 입시 뉴스 요약\n\n{summary}")
