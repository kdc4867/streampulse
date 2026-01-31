import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

import duckdb
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DUCK_PATH = os.getenv("DB_PATH", "data/analytics.db")
PG_USER = os.getenv("POSTGRES_USER", "user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "password")
PG_DB = os.getenv("POSTGRES_DB", "streampulse_meta")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_date_utc(s: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD to UTC 00:00. Returns None if invalid or None."""
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if not _DATE_RE.match(s):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return None


def _parse_start_end(start: Optional[str], end: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Return (start_utc, end_exclusive_utc). end_exclusive is start of next day."""
    s = _parse_date_utc(start)
    e = _parse_date_utc(end)
    if s is None or e is None or e < s:
        return None, None
    end_exclusive = e + timedelta(days=1)
    return s, end_exclusive


def _get_connection(retries=3, backoff=0.2):
    last_err = None
    for attempt in range(retries):
        try:
            return duckdb.connect(DUCK_PATH, read_only=True)
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            raise last_err

def _normalize_records(records):
    normalized = []
    for rec in records:
        out = {}
        for key, value in rec.items():
            if isinstance(value, (pd.Timestamp, datetime)):
                out[key] = value.isoformat()
            elif isinstance(value, np.generic):
                out[key] = value.item()
            else:
                out[key] = value
        normalized.append(out)
    return normalized

def _df_to_records(df):
    if df is None or df.empty:
        return []
    df = df.replace({np.nan: None})
    return _normalize_records(df.to_dict(orient="records"))

def _parse_top_streamers(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return []
    return []

def get_live_traffic():
    con = _get_connection()
    try:
        since = datetime.utcnow() - timedelta(hours=24)
        query = f"""
            WITH stats AS (
                SELECT platform, ts_utc,
                       COUNT(*) AS row_count,
                       SUM(viewers) AS total_viewers
                FROM traffic_category_snapshot
                WHERE ts_utc >= CAST('{since}' AS TIMESTAMP)
                GROUP BY platform, ts_utc
            ),
            latest AS (
                SELECT platform, MAX(ts_utc) AS max_ts
                FROM stats
                WHERE total_viewers > 0 AND row_count > 0
                GROUP BY platform
            )
            SELECT t.platform, t.category_name, t.viewers, t.top_streamers_detail, t.ts_utc
            FROM traffic_category_snapshot t
            JOIN latest l
              ON t.platform = l.platform
             AND t.ts_utc = l.max_ts
            ORDER BY t.viewers DESC
        """
        df = con.execute(query).df()
        if df.empty:
            fallback = f"""
                WITH latest AS (
                    SELECT platform, MAX(ts_utc) AS max_ts
                    FROM traffic_category_snapshot
                    WHERE ts_utc >= CAST('{since}' AS TIMESTAMP)
                    GROUP BY platform
                )
                SELECT t.platform, t.category_name, t.viewers, t.top_streamers_detail, t.ts_utc
                FROM traffic_category_snapshot t
                JOIN latest l
                  ON t.platform = l.platform
                 AND t.ts_utc = l.max_ts
                ORDER BY t.viewers DESC
            """
            df = con.execute(fallback).df()
        if not df.empty:
            df["top_streamers_detail"] = df["top_streamers_detail"].apply(_parse_top_streamers)
        return _df_to_records(df)
    finally:
        con.close()

def get_trend_data(category_name: str, hours: int = 12, start: Optional[str] = None, end: Optional[str] = None):
    con = _get_connection()
    try:
        if start and end:
            start_dt, end_dt = _parse_start_end(start, end)
            if start_dt is None or end_dt is None:
                return []
            q = """
                SELECT ts_utc, platform, viewers, top_streamers_detail
                FROM traffic_category_snapshot
                WHERE category_name = ? AND ts_utc >= ? AND ts_utc < ?
                ORDER BY ts_utc ASC
            """
            df = con.execute(q, [category_name, start_dt, end_dt]).df()
        else:
            since = datetime.utcnow() - timedelta(hours=hours)
            q = """
                SELECT ts_utc, platform, viewers, top_streamers_detail
                FROM traffic_category_snapshot
                WHERE category_name = ? AND ts_utc >= ?
                ORDER BY ts_utc ASC
            """
            df = con.execute(q, [category_name, since]).df()
        if not df.empty:
            df["top_streamers_detail"] = df["top_streamers_detail"].apply(_parse_top_streamers)
        return _df_to_records(df)
    finally:
        con.close()

def get_events(since: Optional[str] = None, limit: Optional[int] = None):
    try:
        engine = create_engine(PG_URL)
        if since is not None:
            since_dt = _parse_date_utc(since)
            if since_dt is None:
                return []
            lim = min(int(limit or 100), 500)
            q = text(
                "SELECT * FROM signal_events WHERE created_at >= :since ORDER BY created_at DESC LIMIT :lim"
            )
            df = pd.read_sql(q, engine, params={"since": since_dt, "lim": lim})
        else:
            q = text("SELECT * FROM signal_events ORDER BY created_at DESC LIMIT 20")
            df = pd.read_sql(q, engine)
        return _df_to_records(df)
    except Exception:
        return []

def get_flash_categories(start: Optional[str] = None, end: Optional[str] = None):
    con = _get_connection()
    try:
        ts_check = con.execute("SELECT MAX(ts_utc) FROM traffic_category_snapshot").fetchone()
        if not ts_check or not ts_check[0]:
            return []
        last_ts = ts_check[0]
        if start and end:
            start_dt, end_dt = _parse_start_end(start, end)
            if start_dt is None or end_dt is None:
                return []
            q = """
                WITH stats AS (
                    SELECT
                        platform, category_name,
                        MAX(viewers) as peak_viewers,
                        ARG_MAX(top_streamers_detail, viewers) as peak_streamer_json,
                        COUNT(DISTINCT CAST(ts_utc AS DATE)) FILTER (WHERE viewers > 1000) as active_days
                    FROM traffic_category_snapshot
                    WHERE ts_utc >= ? AND ts_utc < ?
                    GROUP BY platform, category_name
                ),
                current_status AS (
                    SELECT platform, category_name, viewers as curr_viewers, top_streamers_detail as curr_streamer_json
                    FROM traffic_category_snapshot
                    WHERE ts_utc = ?
                )
                SELECT
                    s.platform, s.category_name, s.peak_viewers, s.active_days, s.peak_streamer_json,
                    c.curr_viewers, c.curr_streamer_json
                FROM stats s
                JOIN current_status c ON s.platform = c.platform AND s.category_name = c.category_name
                WHERE s.peak_viewers > 2000
                  AND s.active_days < 5
                  AND c.curr_viewers < 300
                ORDER BY s.peak_viewers DESC
                LIMIT 50
            """
            df = con.execute(q, [start_dt, end_dt, last_ts]).df()
        else:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            q = """
                WITH stats AS (
                    SELECT
                        platform, category_name,
                        MAX(viewers) as peak_viewers,
                        ARG_MAX(top_streamers_detail, viewers) as peak_streamer_json,
                        COUNT(DISTINCT CAST(ts_utc AS DATE)) FILTER (WHERE viewers > 1000) as active_days
                    FROM traffic_category_snapshot
                    WHERE ts_utc >= ?
                    GROUP BY platform, category_name
                ),
                current_status AS (
                    SELECT platform, category_name, viewers as curr_viewers, top_streamers_detail as curr_streamer_json
                    FROM traffic_category_snapshot
                    WHERE ts_utc = ?
                )
                SELECT
                    s.platform, s.category_name, s.peak_viewers, s.active_days, s.peak_streamer_json,
                    c.curr_viewers, c.curr_streamer_json
                FROM stats s
                JOIN current_status c ON s.platform = c.platform AND s.category_name = c.category_name
                WHERE s.peak_viewers > 2000
                  AND s.active_days < 5
                  AND c.curr_viewers < 300
                ORDER BY s.peak_viewers DESC
                LIMIT 50
            """
            df = con.execute(q, [thirty_days_ago, last_ts]).df()
        if df.empty:
            return []

        def extract_name(json_str):
            try:
                if not json_str:
                    return "-"
                data = json.loads(json_str) if isinstance(json_str, str) else json_str
                if isinstance(data, list) and len(data) > 0:
                    return data[0].get("name", "-")
                return "-"
            except Exception:
                return "-"

        df["peak_contributor"] = df["peak_streamer_json"].apply(extract_name)
        df["current_broadcaster"] = df["curr_streamer_json"].apply(extract_name)
        return _df_to_records(df)
    finally:
        con.close()

def get_daily_category_top(start: Optional[str] = None, end: Optional[str] = None):
    con = _get_connection()
    try:
        if start and end:
            start_dt, end_dt = _parse_start_end(start, end)
            if start_dt is None or end_dt is None:
                return []
            q = """
                SELECT platform, category_name,
                       CAST(AVG(viewers) AS INT) as avg_viewers,
                       MAX(viewers) as peak_viewers
                FROM traffic_category_snapshot
                WHERE ts_utc >= ? AND ts_utc < ?
                GROUP BY platform, category_name
                ORDER BY avg_viewers DESC
            """
            df = con.execute(q, [start_dt, end_dt]).df()
        else:
            yesterday = datetime.utcnow() - timedelta(days=1)
            q = """
                SELECT platform, category_name,
                       CAST(AVG(viewers) AS INT) as avg_viewers,
                       MAX(viewers) as peak_viewers
                FROM traffic_category_snapshot
                WHERE ts_utc >= ?
                GROUP BY platform, category_name
                ORDER BY avg_viewers DESC
            """
            df = con.execute(q, [yesterday]).df()
        return _df_to_records(df)
    finally:
        con.close()

def get_king_of_streamers(start: Optional[str] = None, end: Optional[str] = None):
    con = _get_connection()
    try:
        if start and end:
            start_dt, end_dt = _parse_start_end(start, end)
            if start_dt is None or end_dt is None:
                return []
            q = """
                SELECT platform, category_name, top_streamers_detail, ts_utc
                FROM traffic_category_snapshot
                WHERE ts_utc >= ? AND ts_utc < ?
            """
            df_raw = con.execute(q, [start_dt, end_dt]).df()
        else:
            yesterday = datetime.utcnow() - timedelta(days=1)
            q = """
                SELECT platform, category_name, top_streamers_detail, ts_utc
                FROM traffic_category_snapshot
                WHERE ts_utc >= ?
            """
            df_raw = con.execute(q, [yesterday]).df()

        streamer_list = []
        for _, row in df_raw.iterrows():
            if row["top_streamers_detail"]:
                try:
                    details = row["top_streamers_detail"]
                    if isinstance(details, str):
                        details = json.loads(details)
                    if isinstance(details, list):
                        for d in details:
                            cat_name = row["category_name"] or ""
                            if not cat_name.strip():
                                cat_name = "[General/Talk]"
                            streamer_list.append({
                                "platform": row["platform"],
                                "category": cat_name,
                                "streamer": d.get("name", "Unknown"),
                                "title": d.get("title", ""),
                                "viewers": int(d.get("viewers", 0)),
                                "timestamp": row["ts_utc"]
                            })
                except Exception:
                    continue

        if not streamer_list:
            return []

        df_streamers = pd.DataFrame(streamer_list)
        idx = df_streamers.groupby(["platform", "streamer", "category"])["viewers"].idxmax()
        df_ranking = df_streamers.loc[idx].sort_values(by="viewers", ascending=False)
        return _df_to_records(df_ranking)
    finally:
        con.close()

def get_new_categories():
    con = _get_connection()
    try:
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        past_start = yesterday - timedelta(days=7)
        query = f"""
            WITH today_cats AS (
                SELECT DISTINCT platform, category_name
                FROM traffic_category_snapshot
                WHERE ts_utc >= CAST('{yesterday}' AS TIMESTAMP)
            ),
            past_history AS (
                SELECT DISTINCT platform, category_name
                FROM traffic_category_snapshot
                WHERE ts_utc BETWEEN CAST('{past_start}' AS TIMESTAMP) AND CAST('{yesterday}' AS TIMESTAMP)
            )
            SELECT t.platform, t.category_name
            FROM today_cats t
            LEFT JOIN past_history p ON t.platform = p.platform AND t.category_name = p.category_name
            WHERE p.category_name IS NULL
            LIMIT 20
        """
        df = con.execute(query).df()
        return _df_to_records(df)
    finally:
        con.close()

def get_volatility_metrics(start: Optional[str] = None, end: Optional[str] = None):
    con = _get_connection()
    try:
        if start and end:
            start_dt, end_dt = _parse_start_end(start, end)
            if start_dt is None or end_dt is None:
                return []
            q = """
                SELECT platform, category_name,
                       CAST(AVG(viewers) AS INT) as avg_v,
                       (STDDEV(viewers) / NULLIF(AVG(viewers),0)) as volatility_index
                FROM traffic_category_snapshot
                WHERE ts_utc >= ? AND ts_utc < ?
                GROUP BY 1, 2
                HAVING avg_v > 500
            """
            df = con.execute(q, [start_dt, end_dt]).df()
        else:
            yesterday = datetime.utcnow() - timedelta(days=1)
            q = """
                SELECT platform, category_name,
                       CAST(AVG(viewers) AS INT) as avg_v,
                       (STDDEV(viewers) / NULLIF(AVG(viewers),0)) as volatility_index
                FROM traffic_category_snapshot
                WHERE ts_utc >= ?
                GROUP BY 1, 2
                HAVING avg_v > 500
            """
            df = con.execute(q, [yesterday]).df()
        return _df_to_records(df)
    finally:
        con.close()


def get_insights_period(start: str, end: str) -> dict:
    """기간 내 signal_events 집계: total, by_platform, by_event_type."""
    start_dt, end_dt = _parse_start_end(start, end)
    if start_dt is None or end_dt is None:
        return {
            "total_events": 0,
            "by_platform": {},
            "by_event_type": {},
            "start": start,
            "end": end,
        }
    try:
        engine = create_engine(PG_URL)
        q = text("""
            SELECT COUNT(*) as n FROM signal_events
            WHERE created_at >= :s AND created_at < :e
        """)
        total = int(pd.read_sql(q, engine, params={"s": start_dt, "e": end_dt}).iloc[0]["n"])
        q_plat = text("""
            SELECT platform, COUNT(*) as n FROM signal_events
            WHERE created_at >= :s AND created_at < :e
            GROUP BY platform
        """)
        df_plat = pd.read_sql(q_plat, engine, params={"s": start_dt, "e": end_dt})
        by_platform = {str(r["platform"]): int(r["n"]) for _, r in df_plat.iterrows()}
        q_typ = text("""
            SELECT event_type, COUNT(*) as n FROM signal_events
            WHERE created_at >= :s AND created_at < :e
            GROUP BY event_type
        """)
        df_typ = pd.read_sql(q_typ, engine, params={"s": start_dt, "e": end_dt})
        by_event_type = {str(r["event_type"]): int(r["n"]) for _, r in df_typ.iterrows()}
        return {
            "total_events": total,
            "by_platform": by_platform,
            "by_event_type": by_event_type,
            "start": start,
            "end": end,
        }
    except Exception:
        return {
            "total_events": 0,
            "by_platform": {},
            "by_event_type": {},
            "start": start,
            "end": end,
        }
