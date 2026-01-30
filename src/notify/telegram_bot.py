import os
import requests
import logging

logger = logging.getLogger("telegram_bot")

def send_telegram_message(message: str, *, raise_on_failure: bool = False):
    """
    텔레그램 메시지 전송 함수
    raise_on_failure: True면 실패 시 예외 발생 (Agent Worker용, 원인 추적용)
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
    }
    parse_mode = os.getenv("TELEGRAM_PARSE_MODE", "").strip()
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code != 200:
            err = RuntimeError(f"Telegram API {response.status_code}: {response.text}")
            logger.error("텔레그램 전송 실패: %s", response.text)
            if raise_on_failure:
                raise err
            return
    except requests.RequestException as e:
        logger.error("텔레그램 에러 발생: %s", e)
        if raise_on_failure:
            raise
