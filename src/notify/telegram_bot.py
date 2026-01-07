import os
import requests
import logging

logger = logging.getLogger("telegram_bot")

def send_telegram_message(message: str):
    """
    텔레그램 메시지 전송 함수
    """
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("🚫 텔레그램 토큰이나 Chat ID가 설정되지 않아 알림을 건너뜁니다.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            logger.error(f"텔레그램 전송 실패: {response.text}")
    except Exception as e:
        logger.error(f"텔레그램 에러 발생: {e}")
