import time
import schedule
import duckdb
import psycopg2
import os
import requests
import json
import numpy as np
from datetime import datetime, timedelta

# === 설정 ===
DUCK_PATH = os.getenv("DB_PATH", "data/analytics.db")
PG_DSN = f"host=postgres dbname={os.getenv('POSTGRES_DB', 'streampulse_meta')} user={os.getenv('POSTGRES_USER', 'user')} password={os.getenv('POSTGRES_PASSWORD', 'password')}"
AGENT_URL = "http://agent:8000/analyze"

# V3 확정 파라미터
MIN_ABSOLUTE_DELTA = 1000   # 최소 증가량 (하한선)
DELTA_RATIO = 0.3           # 동적 델타 비율 (30%)
GROWTH_THRESHOLD = 1.5      # 1.5배 (단기 급등)
SEASONAL_THRESHOLD = 1.2    # 1.2배 (장기 추세 대비)
COOLDOWN_MINUTES = 30       # 재알림 금지

def get_pg_conn():
    return psycopg2.connect(PG_DSN)

def init_db():
    """Postgres 테이블 초기화"""
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        # 이벤트 기록 테이블
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signal_events (
                event_id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT NOW(),
                platform VARCHAR(20),
                category_name VARCHAR(100),
                event_type VARCHAR(50), 
                growth_rate FLOAT,
                cause_detail JSONB
            );
            CREATE INDEX IF NOT EXISTS idx_cool ON signal_events (platform, category_name, created_at);
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Detector] DB Init Fail: {e}")

def check_cooldown(platform, category):
    """쿨타임 체크 (30분)"""
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM signal_events
            WHERE platform = %s AND category_name = %s
              AND created_at >= NOW() - INTERVAL '%s minutes'
        """, (platform, category, COOLDOWN_MINUTES))
        exists = cur.fetchone()
        conn.close()
        return exists is not None
    except Exception:
        return False

def calculate_contribution(cur_view, past_view, cur_top_json, past_top_json):
    """
    [원인 분석 핵심 로직] 증가분 기여율(Incremental Contribution) 계산
    Formula: (Top5_Current_Sum - Top5_Past_Sum) / (Current_Total - Past_Total)
    """
    try:
        # JSON 파싱 및 Top5 합계 계산
        cur_list = json.loads(cur_top_json) if cur_top_json else []
        past_list = json.loads(past_top_json) if past_top_json else []
        
        cur_top_sum = sum([item.get('viewers', 0) for item in cur_list])
        past_top_sum = sum([item.get('viewers', 0) for item in past_list])
        
        # 델타 계산
        total_delta = cur_view - past_view
        top_delta = cur_top_sum - past_top_sum
        
        if total_delta <= 0: return "STRUCTURE_ISSUE", 0.0, cur_list # 하락/보합은 구조 이슈로 침

        contribution = top_delta / total_delta
        
        # 기여율이 50% 넘으면 인물 이슈
        if contribution >= 0.5:
            return "PERSON_ISSUE", contribution, cur_list
        else:
            return "STRUCTURE_ISSUE", contribution, cur_list
            
    except Exception as e:
        print(f"[Calc Error] {e}")
        return "STRUCTURE_ISSUE", 0.0, []

def detect_spikes():
    print(f"\n[Detector] 🔍 V3 로직 분석 시작 ({time.strftime('%H:%M:%S')})")
    
    try:
        duck = duckdb.connect(DUCK_PATH, read_only=True)
        
        # 1. 최신 데이터 시점 확인
        last_row = duck.execute("SELECT MAX(ts_utc) FROM traffic_category_snapshot").fetchone()
        if not last_row or not last_row[0]:
            print("[Detector] 데이터 부족.")
            return
        last_ts = last_row[0]

        # 2. V3 핵심 쿼리 (Median, 7-Day, 24-Hour, Current 한 번에 조회)
        # LEAD/LAG 대신 범위를 사용하여 조인
        query = f"""
        WITH 
        -- 1. 현재 데이터
        curr AS (
            SELECT platform, category_name, viewers, top_streamers_detail, ts_utc
            FROM traffic_category_snapshot 
            WHERE ts_utc = CAST('{last_ts}' AS TIMESTAMP)
        ),
        -- 2. 단기 베이스라인 (직전 60분 중앙값)
        short_term AS (
            SELECT platform, category_name, MEDIAN(viewers) as median_60m, 
                   FIRST(viewers) as view_1h_ago, FIRST(top_streamers_detail) as top_1h_ago
            FROM traffic_category_snapshot
            WHERE ts_utc BETWEEN CAST('{last_ts}' AS TIMESTAMP) - INTERVAL 60 MINUTE 
                             AND CAST('{last_ts}' AS TIMESTAMP)
            GROUP BY platform, category_name
        ),
        -- 3. 장기 베이스라인 A (7일 전)
        seasonal_7d AS (
            SELECT platform, category_name, AVG(viewers) as avg_7d
            FROM traffic_category_snapshot
            WHERE ts_utc BETWEEN CAST('{last_ts}' AS TIMESTAMP) - INTERVAL 169 HOUR 
                             AND CAST('{last_ts}' AS TIMESTAMP) - INTERVAL 167 HOUR
            GROUP BY platform, category_name
        ),
        -- 4. 장기 베이스라인 B (24시간 전 - Fallback용)
        seasonal_24h AS (
            SELECT platform, category_name, AVG(viewers) as avg_24h
            FROM traffic_category_snapshot
            WHERE ts_utc BETWEEN CAST('{last_ts}' AS TIMESTAMP) - INTERVAL 25 HOUR 
                             AND CAST('{last_ts}' AS TIMESTAMP) - INTERVAL 23 HOUR
            GROUP BY platform, category_name
        )
        SELECT 
            c.platform, c.category_name, c.viewers,
            s.median_60m, s.view_1h_ago, s.top_1h_ago,
            d7.avg_7d, d24.avg_24h,
            c.top_streamers_detail
        FROM curr c
        LEFT JOIN short_term s ON c.platform = s.platform AND c.category_name = s.category_name
        LEFT JOIN seasonal_7d d7 ON c.platform = d7.platform AND c.category_name = d7.category_name
        LEFT JOIN seasonal_24h d24 ON c.platform = d24.platform AND c.category_name = d24.category_name
        WHERE c.viewers >= {MIN_ABSOLUTE_DELTA}
        """
        
        rows = duck.execute(query).fetchall()
        duck.close()

        alerts = 0
        for row in rows:
            platform, cat, cur_view, med_60m, view_1h, top_1h, avg_7d, avg_24h, top_cur = row
            
            # --- [Logic] Baseline 결정 (우선순위: 7일 -> 24시간 -> 현재의 80%) ---
            if avg_7d:
                seasonal_base = avg_7d
            elif avg_24h:
                seasonal_base = avg_24h
            else:
                seasonal_base = cur_view * 0.8 # Cold Start Fallback
            
            if not med_60m: med_60m = cur_view * 0.8
            if not view_1h: view_1h = cur_view * 0.8

            # --- [Logic] 스파이크 판별 ---
            # 1. 동적 델타 임계값
            dynamic_delta_req = max(MIN_ABSOLUTE_DELTA, seasonal_base * DELTA_RATIO)
            actual_delta = cur_view - seasonal_base
            
            growth_ratio = cur_view / med_60m if med_60m > 0 else 0.
            # 2. 조건 검사
            cond_short = cur_view >= med_60m * GROWTH_THRESHOLD
            cond_season = cur_view >= seasonal_base * SEASONAL_THRESHOLD
            cond_delta = actual_delta >= dynamic_delta_req

            # [추가] 모니터링 로그: 1.2배는 넘었는데 1.5배(기준)는 안 된 애들 구경하기
            if growth_ratio >= 1.2 and growth_ratio < GROWTH_THRESHOLD:
                print(f"👀 [관심] {platform} {cat}: {cur_view}명 (평소 {int(med_60m)}명, {growth_ratio:.2f}배) -> 기준 미달로 탈락")

            if cond_short and cond_season and cond_delta:
                # 3. 쿨타임
                if check_cooldown(platform, cat):
                    continue

                # 4. 원인 분석 (Contribution)
                cause, ratio, clue_list = calculate_contribution(cur_view, view_1h, top_cur, top_1h)
                
                print(f"🚨 [SPIKE] {platform} {cat}: {cur_view}명 (기여율: {ratio*100:.1f}% -> {cause})")

                # 5. 기록 및 에이전트 요청
                event_detail = {
                    "stats": {
                        "current": cur_view, 
                        "baseline_season": int(seasonal_base),
                        "delta": int(actual_delta)
                    },
                    "clues": clue_list[:3] # 상위 3명만 전달
                }
                
                try:
                    conn = get_pg_conn()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO signal_events (platform, category_name, event_type, growth_rate, cause_detail)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (platform, cat, cause, round(cur_view/seasonal_base, 2), json.dumps(event_detail)))
                    conn.commit()
                    conn.close()
                    
                    # Agent 호출 (Fire & Forget)
                    # requests.post(AGENT_URL, json={
                    #     "platform": platform, "category": cat,
                    #     "cause_type": cause, "stats": event_detail['stats'],
                    #     "top_clues": clue_list
                    # }, timeout=1)
                    alerts += 1
                except Exception as e:
                    print(f"❌ Alert Fail: {e}")

        if alerts > 0:
            print(f"[Detector] {alerts}건 감지 완료.")
        else:
            print("[Detector] 특이사항 없음.")

    except Exception as e:
        print(f"[Detector] Error: {e}")

def run():
    print("👀 [Signal Detector V3] 가동 - (Weekly/Median/Delta)")
    time.sleep(5)
    init_db()
    schedule.every(5).minutes.do(detect_spikes)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    run()