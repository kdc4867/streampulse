import time
import schedule
import logging
from src.collectors import soop, chzzk
from src.storage.duckdb_store import DuckDBStore
from src.notify.telegram_bot import send_telegram_message

# DB 저장소 초기화
store = DuckDBStore()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def job_basic_collection():
    """
    [통합 수집] 5분마다 실행
    """
    logging.info("[Runner] === 수집 시작 (%s) ===", time.strftime("%H:%M:%S"))
    
    # 1. SOOP 수집 (Top 5 포함)
    try:
        data_soop = soop.fetch_categories()
        store.save_category_snapshot(data_soop)
    except Exception as e:
        logging.exception("[Runner] SOOP 수집 실패: %s", e)

    # 2. CHZZK 수집 (Top 5 포함)
    try:
        data_chzzk = chzzk.fetch_categories()
        store.save_category_snapshot(data_chzzk)
    except Exception as e:
        logging.exception("[Runner] CHZZK 수집 실패: %s", e)
        
    logging.info("[Runner] === 수집 종료 ===")

def job_health_check():
    """4시간마다 생존 신고"""
    logging.info("[System] 🏥 정기 생존 신고")
    send_telegram_message("🏥 **[StreamPulse]** 시스템 정상 가동 중입니다.\n(4시간 주기 점검)")

def run_scheduler():
    logging.info("🚀 [StreamPulse V3] Collector 시작 (5분 주기)")

    # 서버 시작 알림
    send_telegram_message("🚀 **[StreamPulse V3]** 수집 서버(Collector)가 시작되었습니다!")

    # 시작 즉시 실행
    job_basic_collection()

    # 5분 주기 스케줄 + 4시간 주기 생존 체크
    schedule.every(5).minutes.do(job_basic_collection)
    schedule.every(4).hours.do(job_health_check)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
