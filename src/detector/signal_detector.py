import time
import schedule
import duckdb
import psycopg2
import os
import requests
import json
import numpy as np
import logging
from datetime import datetime, timedelta
from src.notify.telegram_bot import send_telegram_message

DUCK_PATH = os.getenv("DB_PATH", "data/analytics.db")
_default_pg_host = "postgres" if os.path.exists("/.dockerenv") else "localhost"
PG_HOST = os.getenv("POSTGRES_HOST", _default_pg_host)
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DSN = (
    f"host={PG_HOST} port={PG_PORT} "
    f"dbname={os.getenv('POSTGRES_DB', 'streampulse_meta')} "
    f"user={os.getenv('POSTGRES_USER', 'user')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'password')}"
)
AGENT_URL = "http://agent:8000/analyze"

MIN_ABSOLUTE_DELTA = 1500   # 최소 증가량 (하한선)
DELTA_RATIO = 0.3           # 동적 델타 비율 (30%)
GROWTH_THRESHOLD = 1.7      # 1.7배 (단기 급등)
SEASONAL_THRESHOLD = 1.2    # 1.2배 (장기 추세 대비)
COOLDOWN_MINUTES = 30       # 재알림 금지
CANDIDATE_COOLDOWN_MINUTES = int(os.getenv("CANDIDATE_COOLDOWN_MINUTES", "120"))
BASELINE_FLOOR = 300        # 기준 시청자 하한선
INTEREST_GROWTH = float(os.getenv("INTEREST_GROWTH", "1.2"))
INTEREST_DELTA = int(os.getenv("INTEREST_DELTA", "500"))
INTEREST_TOP_N = int(os.getenv("INTEREST_TOP_N", "10"))
MAJOR_TOP_N = int(os.getenv("MAJOR_TOP_N", "12"))
MAJOR_GROWTH_THRESHOLD = float(
    os.getenv("MAJOR_GROWTH_THRESHOLD", str(GROWTH_THRESHOLD - 0.2))
)
ALERT_MODE = os.getenv("DETECTOR_ALERT_MODE", "post_research")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def get_pg_conn():
    return psycopg2.connect(PG_DSN)

def init_db():
    """Postgres 테이블 초기화"""
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS signal_events (
                event_id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT NOW(),
                platform VARCHAR(20),
                category_name VARCHAR(100),
                event_type VARCHAR(50), 
                growth_rate FLOAT,
                cause_detail JSONB,
                analysis_status VARCHAR(20),
                analysis_tier VARCHAR(10),
                spike_reason TEXT,
                entity_keywords JSONB,
                context_cache_key TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_cool ON signal_events (platform, category_name, created_at);
            CREATE INDEX IF NOT EXISTS idx_signal_events_created_at ON signal_events (created_at DESC);
        """)
        cur.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS analysis_status VARCHAR(20)")
        cur.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS analysis_tier VARCHAR(10)")
        cur.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS spike_reason TEXT")
        cur.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS entity_keywords JSONB")
        cur.execute("ALTER TABLE signal_events ADD COLUMN IF NOT EXISTS context_cache_key TEXT")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Detector] DB Init Fail: {e}")

def check_cooldown(platform, category, minutes):
    """쿨타임 체크 (30분)"""
    try:
        conn = get_pg_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT 1 FROM signal_events
            WHERE platform = %s AND category_name = %s
              AND created_at >= NOW() - INTERVAL '%s minutes'
        """, (platform, category, minutes))
        exists = cur.fetchone()
        conn.close()
        return exists is not None
    except Exception:
        return False

def calculate_contribution(cur_view, past_view, cur_top_json, past_top_json):
    """
    [원인 분석 핵심 로직] 증가분 기여율 계산
    공식: (Top5_Current_Sum - Top5_Past_Sum) / (Current_Total - Past_Total)
    """
    try:
        cur_list = json.loads(cur_top_json) if cur_top_json else []
        past_list = json.loads(past_top_json) if past_top_json else []
        
        cur_top_sum = sum([item.get('viewers', 0) for item in cur_list])
        past_top_sum = sum([item.get('viewers', 0) for item in past_list])
        
        total_delta = cur_view - past_view
        top_delta = cur_top_sum - past_top_sum
        
        # 하락/보합은 구조 이슈로 분류
        if total_delta <= 0:
            return "STRUCTURE_ISSUE", 0.0, cur_list

        contribution = top_delta / total_delta
        
        # 기여율이 높으면 인물 이슈로 분류
        if contribution >= 0.5:
            return "PERSON_ISSUE", contribution, cur_list
        else:
            return "STRUCTURE_ISSUE", contribution, cur_list
            
    except Exception as e:
        print(f"[Calc Error] {e}")
        return "STRUCTURE_ISSUE", 0.0, []

def parse_top_list(value):
    if not value:
        return []
    try:
        return json.loads(value) if isinstance(value, str) else value
    except Exception:
        return []

def extract_top1_viewers(top_list):
    if not top_list:
        return 0
    return int(top_list[0].get("viewers", 0) or 0)

def sum_top2_5_viewers(top_list):
    if not top_list or len(top_list) < 2:
        return 0
    return sum(int(item.get("viewers", 0) or 0) for item in top_list[1:5])

def detect_spikes():
    print(f"\n[Detector] 🔍 V3 로직 분석 시작 ({time.strftime('%H:%M:%S')})")
    
    try:
        duck = duckdb.connect(DUCK_PATH, read_only=True)
        
        last_rows = duck.execute(
            "SELECT platform, MAX(ts_utc) AS ts FROM traffic_category_snapshot GROUP BY platform"
        ).fetchall()
        if not last_rows:
            print("[Detector] 데이터 부족.")
            return

        # 스파이크 판정을 위한 기준선/단기/장기 지표를 한 번에 조회
        query = f"""
        WITH 
        -- 0. 플랫폼별 최신 시각
        last_ts AS (
            SELECT platform, MAX(ts_utc) AS ts
            FROM traffic_category_snapshot
            GROUP BY platform
        ),
        -- 1. 현재 데이터 (플랫폼별 최신 스냅샷)
        curr AS (
            SELECT t.platform, t.category_name, t.viewers, t.open_lives, t.top_streamers_detail, t.ts_utc
            FROM traffic_category_snapshot t
            JOIN last_ts lt ON t.platform = lt.platform AND t.ts_utc = lt.ts
        ),
        -- 2. 단기 베이스라인 (직전 60분 중앙값)
        short_term AS (
            SELECT t.platform, t.category_name, MEDIAN(t.viewers) as median_60m, 
                   FIRST(t.viewers) as view_1h_ago, FIRST(t.open_lives) as open_1h_ago,
                   FIRST(t.top_streamers_detail) as top_1h_ago
            FROM traffic_category_snapshot t
            JOIN last_ts lt ON t.platform = lt.platform
            WHERE t.ts_utc BETWEEN lt.ts - INTERVAL 60 MINUTE 
                             AND lt.ts
            GROUP BY t.platform, t.category_name
        ),
        -- 3. 장기 베이스라인 A (7일 전, 동일 시간대 ±2시간)
        seasonal_7d AS (
            SELECT t.platform, t.category_name, AVG(t.viewers) as avg_7d
            FROM traffic_category_snapshot t
            JOIN last_ts lt ON t.platform = lt.platform
            WHERE t.ts_utc BETWEEN lt.ts - INTERVAL 170 HOUR 
                             AND lt.ts - INTERVAL 166 HOUR
            GROUP BY t.platform, t.category_name
        ),
        -- 4. 장기 베이스라인 B (전날 동일 시간대 ±2시간)
        seasonal_24h AS (
            SELECT t.platform, t.category_name, AVG(t.viewers) as avg_24h
            FROM traffic_category_snapshot t
            JOIN last_ts lt ON t.platform = lt.platform
            WHERE t.ts_utc BETWEEN lt.ts - INTERVAL 26 HOUR 
                             AND lt.ts - INTERVAL 22 HOUR
            GROUP BY t.platform, t.category_name
        )
        SELECT 
            c.platform, c.category_name, c.viewers, c.open_lives,
            s.median_60m, s.view_1h_ago, s.open_1h_ago, s.top_1h_ago,
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

        records = []
        for row in rows:
            platform, cat, cur_view, open_now, med_60m, view_1h, open_1h, top_1h, avg_7d, avg_24h, top_cur = row

            if avg_7d:
                seasonal_base = avg_7d
            elif avg_24h:
                seasonal_base = avg_24h
            else:
                seasonal_base = cur_view * 0.8

            if not med_60m:
                med_60m = cur_view * 0.8
            if not view_1h:
                view_1h = cur_view * 0.8

            if seasonal_base < BASELINE_FLOOR:
                continue

            dynamic_delta_req = max(MIN_ABSOLUTE_DELTA, seasonal_base * DELTA_RATIO)
            actual_delta = max(0, int(round(cur_view - seasonal_base)))
            growth_ratio = cur_view / med_60m if med_60m > 0 else 0.0
            season_ratio = cur_view / seasonal_base if seasonal_base > 0 else 0.0

            records.append({
                "platform": platform,
                "category": cat,
                "cur_view": cur_view,
                "open_now": open_now,
                "med_60m": med_60m,
                "view_1h": view_1h,
                "open_1h": open_1h,
                "top_1h": top_1h,
                "seasonal_base": seasonal_base,
                "growth_ratio": growth_ratio,
                "season_ratio": season_ratio,
                "dynamic_delta_req": dynamic_delta_req,
                "actual_delta": actual_delta,
                "top_cur": top_cur,
            })

        major_set = set()
        by_platform = {}
        for rec in records:
            by_platform.setdefault(rec["platform"], []).append(rec)
        for platform, recs in by_platform.items():
            recs_sorted = sorted(recs, key=lambda r: r["seasonal_base"], reverse=True)
            for rec in recs_sorted[:MAJOR_TOP_N]:
                major_set.add((platform, rec["category"]))

        interest_keys = set()
        for rec in records:
            if rec["growth_ratio"] >= INTEREST_GROWTH and rec["actual_delta"] >= INTEREST_DELTA:
                interest_keys.add((rec["platform"], rec["category"]))
        delta_candidates = [r for r in records if r["actual_delta"] > 0]
        ratio_candidates = [r for r in records if r["growth_ratio"] > 1.0 and r["actual_delta"] > 0]
        top_by_delta = sorted(delta_candidates, key=lambda r: r["actual_delta"], reverse=True)[:INTEREST_TOP_N]
        top_by_ratio = sorted(ratio_candidates, key=lambda r: r["growth_ratio"], reverse=True)[:INTEREST_TOP_N]
        top_delta_keys = {(r["platform"], r["category"]) for r in top_by_delta}
        top_ratio_keys = {(r["platform"], r["category"]) for r in top_by_ratio}
        interest_keys |= top_delta_keys | top_ratio_keys

        alerts = 0
        for rec in records:
            platform = rec["platform"]
            cat = rec["category"]
            cur_view = rec["cur_view"]
            med_60m = rec["med_60m"]
            seasonal_base = rec["seasonal_base"]
            growth_ratio = rec["growth_ratio"]
            season_ratio = rec["season_ratio"]
            dynamic_delta_req = rec["dynamic_delta_req"]
            actual_delta = rec["actual_delta"]

            is_major = (platform, cat) in major_set
            growth_threshold = MAJOR_GROWTH_THRESHOLD if is_major else GROWTH_THRESHOLD
            cond_short = cur_view >= med_60m * growth_threshold
            cond_season = cur_view >= seasonal_base * SEASONAL_THRESHOLD
            cond_delta = actual_delta >= dynamic_delta_req

            if actual_delta <= 0:
                continue

            signal_level = None
            candidate_reasons = []
            key = (platform, cat)

            if cond_short and cond_season and cond_delta:
                signal_level = "SPIKE"
            elif key in interest_keys:
                signal_level = "CANDIDATE"
                if growth_ratio >= INTEREST_GROWTH and actual_delta >= INTEREST_DELTA:
                    candidate_reasons.append("ratio_delta")
                if key in top_delta_keys:
                    candidate_reasons.append("top_delta")
                if key in top_ratio_keys:
                    candidate_reasons.append("top_ratio")
            else:
                if growth_ratio >= INTEREST_GROWTH and growth_ratio < growth_threshold:
                    print(
                        f"👀 [관심] {platform} {cat}: {cur_view}명 "
                        f"(평소 {int(med_60m)}명, {growth_ratio:.2f}배) -> 기준 미달로 탈락"
                    )
                continue

            cooldown_minutes = (
                CANDIDATE_COOLDOWN_MINUTES
                if signal_level == "CANDIDATE"
                else COOLDOWN_MINUTES
            )
            if check_cooldown(platform, cat, cooldown_minutes):
                continue

            cause, ratio, clue_list = calculate_contribution(
                cur_view, rec["view_1h"], rec["top_cur"], rec["top_1h"]
            )
            top_list = parse_top_list(rec["top_cur"])
            past_top_list = parse_top_list(rec["top_1h"])
            top1_viewers = extract_top1_viewers(top_list)
            dominance_index = (top1_viewers / cur_view) if cur_view else 0
            open_delta = (
                (rec["open_now"] - rec["open_1h"])
                if rec["open_now"] is not None and rec["open_1h"] is not None
                else None
            )
            top2_5_current = sum_top2_5_viewers(top_list)
            top2_5_baseline = sum_top2_5_viewers(past_top_list)
            top2_5_delta = top2_5_current - top2_5_baseline
            market_proof = False
            if open_delta is not None and open_delta >= 3:
                market_proof = True
            if top2_5_baseline > 0:
                if top2_5_current >= top2_5_baseline * 1.2 and top2_5_delta >= 500:
                    market_proof = True

            classification = cause
            early_exit = False
            if dominance_index >= 0.85 and not market_proof:
                classification = "CATEGORY_ADOPTION"
                early_exit = True

            if signal_level == "SPIKE" and classification == "PERSON_ISSUE":
                stricter_delta = max(1500, seasonal_base * 0.5)
                if growth_ratio < 2.0 or actual_delta < stricter_delta:
                    print(
                        f"⚠️ [PERSON 보정] {platform} {cat}: "
                        f"growth={growth_ratio:.2f}, delta={int(actual_delta)} -> 기준 미달"
                    )
                    continue

            label = "🚨 [SPIKE]" if signal_level == "SPIKE" else "👀 [후보]"
            print(
                f"{label} {platform} {cat}: {cur_view}명 "
                f"(기여율: {ratio*100:.1f}% -> {classification})"
            )

            event_detail = {
                "signal_level": signal_level,
                "candidate_reasons": candidate_reasons,
                "stats": {
                    "current": cur_view,
                    "baseline_season": int(round(seasonal_base)),
                    "delta": actual_delta,
                    "growth_ratio": round(growth_ratio, 2),
                    "season_ratio": round(season_ratio, 2),
                    "delta_req": int(round(dynamic_delta_req)),
                    "major_category": is_major,
                    "major_growth_threshold": growth_threshold,
                },
                "market": {
                    "dominance_index": dominance_index,
                    "top1_viewers": top1_viewers,
                    "open_lives": rec["open_now"],
                    "open_lives_1h": rec["open_1h"],
                    "open_lives_delta": open_delta,
                    "top2_5_current": top2_5_current,
                    "top2_5_baseline": top2_5_baseline,
                    "top2_5_delta": top2_5_delta,
                    "market_proof": market_proof,
                    "early_exit": early_exit,
                },
                "clues": clue_list[:3],
            }

            try:
                analysis_status = "SKIPPED" if classification == "CATEGORY_ADOPTION" else "PENDING"
                analysis_tier = "NONE"
                conn = get_pg_conn()
                cur = conn.cursor()
                cur.execute(
                    """
                        INSERT INTO signal_events
                            (platform, category_name, event_type, growth_rate, cause_detail, analysis_status, analysis_tier)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        platform,
                        cat,
                        classification,
                        round(cur_view / seasonal_base, 2),
                        json.dumps(event_detail),
                        analysis_status,
                        analysis_tier,
                    ),
                )
                conn.commit()
                conn.close()

                if (
                    signal_level == "SPIKE"
                    and classification != "CATEGORY_ADOPTION"
                    and ALERT_MODE == "immediate"
                ):
                    top_streamer_name = (
                        clue_list[0].get("name", "Unknown") if clue_list else "Unknown"
                    )
                    msg = (
                        f"🚨 **[급등 감지] {platform}**\n"
                        f"카테고리: `{cat}`\n"
                        f"현재 시청자: {cur_view:,}명\n"
                        f"증가량: +{actual_delta:,}명\n"
                        f"기준 시청자: {int(round(seasonal_base)):,}명\n"
                        f"핵심 원인: {top_streamer_name}"
                    )
                    send_telegram_message(msg)
                    logging.info("🚨 [Telegram] %s 알림 전송 완료", cat)

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
