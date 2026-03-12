import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- 설정 구간 ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# 감시 대상 리스트 (이름과 URL)
TARGETS = [
    {
        "name": "공통영어1(오) - 엔이능률",
        "url": "https://www.ktbookmall.com/user/shop/01_normal/list.do?cat=16&code=46212&GroupName=%EA%B3%B5%ED%86%B5%EC%98%81%EC%96%B4%201(22%EA%B0%9C%EC%A0%95)(%EC%A7%80%EB%8F%84%EC%84%9C)"
    },
    {
        "name": "공통영어2(강) - 천재교과서",
        "url": "https://www.ktbookmall.com/user/shop/01_normal/list.do?cat=16&code=46222&GroupName=%EA%B3%B5%ED%86%B5%EC%98%81%EC%96%B4%202(22%EA%B0%9C%EC%A0%95)(%EC%A7%80%EB%8F%84%EC%84%9C)"
    }
]

def send_telegram_msg(text):
    """텔레그램으로 메시지를 보내는 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID, 
        'text': text,
        'disable_web_page_preview': False  # URL 미리보기를 활성화합니다.
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("텔레그램 알림 전송 성공!")
        else:
            print(f"텔레그램 전송 실패 (코드: {response.status_code})")
    except Exception as e:
        print(f"에러 발생: {e}")

def check_stock():
    """사이트를 확인하고 입고 여부를 판단하는 함수"""
    print("--- 입고 확인 프로세스 시작 ---")
    
    for book in TARGETS:
        try:
            # 1. 사이트 접속
            response = requests.get(book['url'])
            response.encoding = 'utf-8' # 한글 깨짐 방지
            
            # 2. 내용 분석
            # 페이지 전체에서 '입고예정'이라는 단어가 사라졌는지 확인
            if "입고예정" not in response.text and book['name'].split('(')[0] in response.text:
                # 3. 메시지 작성 (URL 포함)
                message = (
                    f"🎊 [입고 소식!]\n\n"
                    f"📘 교재명: {book['name']}\n"
                    f"✅ 상태: 입고 완료(또는 상태 변경)\n"
                    f"🔗 구매 링크: {book['url']}"
                )
                send_telegram_msg(message)
                print(f"[{book['name']}] 알림을 보냈습니다.")
            else:
                print(f"[{book['name']}] 아직 '입고예정' 상태입니다.")
                
        except Exception as e:
            print(f"[{book['name']}] 확인 중 에러 발생: {e}")

if __name__ == "__main__":
    check_stock()
