import duckdb
import os
from datetime import datetime

DB_PATH = "data/analytics.db"

def check_health():
    if not os.path.exists(DB_PATH):
        print("❌ DB 파일이 없습니다. 수집기가 안 돌고 있나요?")
        return

    try:
        con = duckdb.connect(DB_PATH, read_only=True)
        
        total_rows = con.execute("SELECT COUNT(*) FROM traffic_category_snapshot").fetchone()[0]
        
        time_range = con.execute("SELECT MIN(ts_utc), MAX(ts_utc) FROM traffic_category_snapshot").fetchone()
        start_time, end_time = time_range
        
        snapshot_count = con.execute("SELECT COUNT(DISTINCT ts_utc) FROM traffic_category_snapshot").fetchone()[0]
        
        print("-" * 30)
        print(f"📊 [StreamPulse] 데이터 수집 현황")
        print("-" * 30)
        print(f"💾 총 데이터 Row 수 : {total_rows:,} 개")
        print(f"⏱️ 수집 횟수 (스냅샷): {snapshot_count:,} 번")
        print(f"📅 시작 시간 (UTC)  : {start_time}")
        print(f"📅 종료 시간 (UTC)  : {end_time}")
        
        print("-" * 30)
        print("🔎 최근 시간대별 수집 빈도 (12번/시간 권장):")
        hourly_stats = con.execute("""
            SELECT 
                strftime(ts_utc, '%Y-%m-%d %H:00:00') as hour_group,
                COUNT(DISTINCT ts_utc) as collect_count
            FROM traffic_category_snapshot
            GROUP BY hour_group
            ORDER BY hour_group DESC
            LIMIT 5
        """).fetchall()
        
        for hour, count in hourly_stats:
            status = "✅ 정상" if count >= 10 else "⚠️ 불안정"
            print(f"   - {hour} : {count}번 수집 ({status})")
            
        con.close()

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    check_health()
