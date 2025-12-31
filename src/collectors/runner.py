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
        # SOOP API가 일시적으로 빈/부분 데이터만 주는 경우가 있어, 이상치는 저장하지 않음.
        soop_count = len(data_soop)
        soop_total = sum(item.get("viewers", 0) for item in data_soop)
        if soop_count < 50 or soop_total < 5000:
            logging.warning(
                "[Runner] SOOP 스냅샷 이상치 감지 (count=%s, total=%s) -> 저장 스킵",
                soop_count,
                soop_total,
            )
        else:
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
    """8시간마다 생존 신고"""
    logging.info("[System] 🏥 정기 생존 신고")
    send_telegram_message("🏥 **[StreamPulse]** 시스템 정상 가동 중입니다.\n(8시간 주기 점검)")

def run_scheduler():
    logging.info("🚀 [StreamPulse V3] Collector 시작 (5분 주기)")

    # 서버 시작 알림
    send_telegram_message("🚀 **[StreamPulse V3]** 수집 서버(Collector)가 시작되었습니다!")

    # 시작 즉시 실행
    job_basic_collection()

    # 5분 주기 스케줄 + 8시간 주기 생존 체크
    schedule.every(5).minutes.do(job_basic_collection)
    schedule.every(8).hours.do(job_health_check)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run_scheduler()
