import time
import schedule
from src.collectors import soop, chzzk
from src.storage.duckdb_store import DuckDBStore

# DB 저장소 초기화
store = DuckDBStore()

def job_collection():
    """
    [통합 수집] 5분마다 실행
    """
    print(f"\n[Runner] === 수집 시작 ({time.strftime('%H:%M:%S')}) ===")
    
    # 1. SOOP 수집 (Top 5 포함)
    try:
        data_soop = soop.fetch_categories()
        store.save_category_snapshot(data_soop)
    except Exception as e:
        print(f"[Runner] SOOP 수집 실패: {e}")

    # 2. CHZZK 수집 (Top 5 포함)
    try:
        data_chzzk = chzzk.fetch_categories()
        store.save_category_snapshot(data_chzzk)
    except Exception as e:
        print(f"[Runner] CHZZK 수집 실패: {e}")
        
    print("[Runner] === 수집 종료 ===\n")

def run():
    print("🚀 [StreamPulse V3] Collector 시작 (5분 주기)")
    
    # 1. 시작 즉시 실행
    job_collection()
    
    # 2. 5분 주기 스케줄
    schedule.every(5).minutes.do(job_collection)
    
    # 3. Loop
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run()