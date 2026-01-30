import json
import os
import time
import logging
import psycopg2

from src.agent.graph import app as agent_app
from src.notify.telegram_bot import send_telegram_message

_default_pg_host = "postgres" if os.path.exists("/.dockerenv") else "localhost"
PG_HOST = os.getenv("POSTGRES_HOST", _default_pg_host)
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DSN = (
    f"host={PG_HOST} port={PG_PORT} "
    f"dbname={os.getenv('POSTGRES_DB', 'streampulse_meta')} "
    f"user={os.getenv('POSTGRES_USER', 'user')} "
    f"password={os.getenv('POSTGRES_PASSWORD', 'password')}"
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
AGENT_ALERT_MODE = os.getenv("AGENT_ALERT_MODE", "confirmed")
ALERT_KEYWORDS = [
    kw.strip() for kw in os.getenv("ALERT_KEYWORDS", "패치,업데이트").split(",") if kw.strip()
]
RESEARCH_MIN_DELTA = int(os.getenv("RESEARCH_MIN_DELTA", "1500"))
RESEARCH_MIN_GROWTH = float(os.getenv("RESEARCH_MIN_GROWTH", "1.4"))
RESEARCH_MIN_SEASON = float(os.getenv("RESEARCH_MIN_SEASON", "1.15"))
RESEARCH_MAJOR_MIN_DELTA = int(os.getenv("RESEARCH_MAJOR_MIN_DELTA", "10000"))
RESEARCH_MAJOR_MIN_GROWTH = float(os.getenv("RESEARCH_MAJOR_MIN_GROWTH", "1.15"))
RESEARCH_MAJOR_MIN_SEASON = float(os.getenv("RESEARCH_MAJOR_MIN_SEASON", "1.10"))
ALERT_MIN_DELTA = int(os.getenv("ALERT_MIN_DELTA", "1500"))
ALERT_MIN_GROWTH = float(os.getenv("ALERT_MIN_GROWTH", "1.3"))
ALERT_MAJOR_MIN_DELTA = int(os.getenv("ALERT_MAJOR_MIN_DELTA", "3000"))
ALERT_MAJOR_MIN_GROWTH = float(os.getenv("ALERT_MAJOR_MIN_GROWTH", "1.5"))

def get_pg_conn():
    return psycopg2.connect(PG_DSN)

def fetch_pending(limit=3):
    conn = get_pg_conn()
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute(
        """
        WITH cte AS (
            SELECT event_id, platform, category_name, event_type, growth_rate, cause_detail
            FROM signal_events
            WHERE analysis_status = 'PENDING'
            ORDER BY created_at ASC
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE signal_events
        SET analysis_status = 'IN_PROGRESS'
        WHERE event_id IN (SELECT event_id FROM cte)
        RETURNING event_id, platform, category_name, event_type, growth_rate, cause_detail
        """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.commit()
    conn.close()
    return rows

def update_event(
    event_id,
    status,
    tier,
    report,
    spike_reason,
    entity_keywords,
    cache_key,
    search_results,
    watcher_output,
    search_queries,
    analyst_output,
    editor_output,
    analysis_verdict,
    analysis_reason,
    evidence_keywords,
    event_kind,
):
    conn = get_pg_conn()
    cur = conn.cursor()
    extra = {
        "ai_report": report,
        "spike_reason": spike_reason,
        "entity_keywords": entity_keywords,
        "search_results": search_results,
        "watcher_output": watcher_output,
        "search_queries": search_queries,
        "analyst_output": analyst_output,
        "editor_output": editor_output,
        "analysis_verdict": analysis_verdict,
        "analysis_reason": analysis_reason,
        "evidence_keywords": evidence_keywords,
        "event_kind": event_kind,
    }
    cur.execute(
        """
        UPDATE signal_events
        SET analysis_status = %s,
            analysis_tier = %s,
            spike_reason = %s,
            entity_keywords = %s::jsonb,
            context_cache_key = %s,
            cause_detail = cause_detail || %s::jsonb
        WHERE event_id = %s
        """,
        (
            status,
            tier,
            spike_reason,
            json.dumps(entity_keywords, ensure_ascii=False),
            cache_key,
            json.dumps(extra, ensure_ascii=False),
            event_id,
        ),
    )
    conn.commit()
    conn.close()

def mark_failed(event_id, error):
    conn = get_pg_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE signal_events
        SET analysis_status = 'FAILED',
            cause_detail = cause_detail || %s::jsonb
        WHERE event_id = %s
        """,
        (json.dumps({"ai_error": str(error)}, ensure_ascii=False), event_id),
    )
    conn.commit()
    conn.close()

def should_research(signal_level, event_type, stats):
    if event_type == "CATEGORY_ADOPTION":
        return False, "category_adoption"
    if signal_level == "SPIKE":
        return True, ""
    if signal_level != "CANDIDATE":
        return False, "not_candidate"
    growth_ratio = float(stats.get("growth_ratio") or 0.0)
    season_ratio = float(stats.get("season_ratio") or 0.0)
    actual_delta = int(stats.get("delta") or 0)
    is_major = bool(stats.get("major_category"))
    min_delta = RESEARCH_MAJOR_MIN_DELTA if is_major else RESEARCH_MIN_DELTA
    min_growth = RESEARCH_MAJOR_MIN_GROWTH if is_major else RESEARCH_MIN_GROWTH
    if growth_ratio < 1.0:
        return False, f"decreasing_trend_(ratio:{growth_ratio:.2f})"
    if actual_delta <= 0:
        return False, "delta_zero"
    if is_major:
        if actual_delta < min_delta:
            return False, "below_research_threshold"
        if growth_ratio < min_growth and season_ratio < RESEARCH_MAJOR_MIN_SEASON:
            return False, "below_research_threshold"
        return True, ""
    if actual_delta < min_delta:
        return False, "below_research_threshold"
    if growth_ratio < min_growth and season_ratio < RESEARCH_MIN_SEASON:
        return False, "below_research_threshold"
    return True, ""

def process_event(row):
    event_id, platform, category_name, event_type, growth_rate, cause_detail = row
    cause = {}
    if cause_detail:
        try:
            cause = json.loads(cause_detail) if isinstance(cause_detail, str) else cause_detail
        except Exception:
            cause = {}
    inputs = {
        "event_id": event_id,
        "platform": platform,
        "category": category_name,
        "event_type": event_type,
        "signal_level": cause.get("signal_level", ""),
        "stats": cause.get("stats", {}),
        "top_clues": cause.get("clues", []),
        "market": cause.get("market", {}),
        "search_results": "",
        "final_report": "",
    }
    stats = cause.get("stats", {})
    signal_level = cause.get("signal_level", "")
    allow_research, skip_reason = should_research(signal_level, event_type, stats)
    action = "리서치" if allow_research else f"스킵(reason={skip_reason})"
    print(f"[Agent] 리서치 대상 event_id={event_id} {platform}/{category_name} signal_level={signal_level} → {action}")
    if not allow_research:
        print(f"[Agent] 리서치 스킵 event_id={event_id} {platform}/{category_name} reason={skip_reason}")
        update_event(
            event_id,
            "SKIPPED",
            "NONE",
            "",
            "",
            [],
            "",
            "",
            {},
            [],
            "",
            "",
            "NO_RESEARCH",
            skip_reason,
            [],
            "",
        )
        return

    print(f"[Agent] 리서치 시작 event_id={event_id} {platform}/{category_name}")
    result = agent_app.invoke(inputs)
    update_event(
        event_id,
        "DONE",
        result.get("analysis_tier", "T1"),
        result.get("final_report", ""),
        result.get("spike_reason", ""),
        result.get("entity_keywords", []),
        result.get("cache_key", ""),
        result.get("search_results", ""),
        result.get("watcher_output", {}),
        result.get("search_queries", []),
        result.get("analyst_output", ""),
        result.get("editor_output", ""),
        result.get("analysis_verdict", ""),
        result.get("analysis_reason", ""),
        result.get("evidence_keywords", []),
        result.get("event_kind", ""),
    )
    signal_level = cause.get("signal_level", "")
    verdict = result.get("analysis_verdict", "")
    event_keywords = result.get("event_keywords", []) or []
    growth_ratio = float(stats.get("growth_ratio") or 0.0)
    actual_delta = int(stats.get("delta") or 0)
    is_major = bool(stats.get("major_category"))
    min_alert_delta = ALERT_MAJOR_MIN_DELTA if is_major else ALERT_MIN_DELTA
    min_alert_growth = ALERT_MAJOR_MIN_GROWTH if is_major else ALERT_MIN_GROWTH
    passes_alert_gate = actual_delta > 0 and actual_delta >= min_alert_delta
    should_alert = False
    if AGENT_ALERT_MODE == "all":
        should_alert = passes_alert_gate
    elif AGENT_ALERT_MODE == "confirmed":
        if verdict == "CONFIRMED" and passes_alert_gate:
            should_alert = True
        elif (
            signal_level == "CANDIDATE"
            and passes_alert_gate
            and any(kw in event_keywords for kw in ALERT_KEYWORDS)
        ):
            should_alert = True

    print(f"[Agent] 리서치 완료 event_id={event_id} {platform}/{category_name} verdict={verdict} passes_gate={passes_alert_gate} should_alert={should_alert}")
    if should_alert:
        try:
            stats = cause.get("stats", {})
            current = int(stats.get("current") or 0)
            baseline = int(stats.get("baseline_season") or 0)
            delta = int(stats.get("delta") or 0)
            reason = result.get("analysis_reason") or result.get("final_report", "")
            event_kind = result.get("event_kind") or ""
            top_clues = cause.get("clues", []) or []
            top_streamer = top_clues[0].get("name", "Unknown") if top_clues else "Unknown"
            msg = (
                f"🚨 **[급등 확정] {platform}**\n"
                f"카테고리: `{category_name}`\n"
                f"현재 시청자: {current:,}명\n"
                f"증가량: +{delta:,}명\n"
                f"기준 시청자: {baseline:,}명\n"
                f"핵심 스트리머: {top_streamer}\n"
                f"판정: {verdict} {event_kind}".strip()
            )
            if reason:
                msg = f"{msg}\n근거: {reason}"
            send_telegram_message(msg, raise_on_failure=True)
            print(f"[Agent] 🚨 알림 발송 event_id={event_id} {platform}/{category_name}")
        except Exception as e:
            logging.exception("❌ [Agent Alert] 텔레그램 전송 실패 (event_id=%s, cat=%s): %s", event_id, category_name, e)
    else:
        print(f"[Agent] 알림 스킵 event_id={event_id} {platform}/{category_name} verdict={verdict} gate={passes_alert_gate} mode={AGENT_ALERT_MODE}")

def run_worker(poll_interval=5):
    logging.info("🤖 [Agent Worker] 시작 (poll=%ss)", poll_interval)
    while True:
        try:
            rows = fetch_pending()
            if not rows:
                time.sleep(poll_interval)
                continue
            print(f"[Agent] PENDING {len(rows)}건 조회 → 리서치 대상")
            for row in rows:
                try:
                    process_event(row)
                except Exception as e:
                    logging.exception("❌ [Agent Worker] 이벤트 처리 실패 (event_id=%s): %s", row[0], e)
                    mark_failed(row[0], e)
        except Exception as e:
            logging.exception("❌ [Agent Worker] 처리 실패: %s", e)
            time.sleep(poll_interval)

if __name__ == "__main__":
    run_worker()
