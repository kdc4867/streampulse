# src/notify/telegram_bot.py
import os
import requests
import logging

logger = logging.getLogger("telegram_bot")

def send_telegram_message(message: str):
    """
    텔레그램 메시지 전송 함수
    """
    # .env에서 불러옴
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        # 로컬 테스트할 때 .env 설정을 까먹었을 경우를 대비해 로그만 남기고 패스
        logger.warning("🚫 텔레그램 토큰이나 Chat ID가 설정되지 않아 알림을 건너뜁니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"  # 굵은 글씨(**) 등을 쓰기 위함
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            logger.error(f"텔레그램 전송 실패: {response.text}")
    except Exception as e:
        logger.error(f"텔레그램 에러 발생: {e}")