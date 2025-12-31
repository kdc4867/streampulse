import json
import os
import time
from datetime import datetime, timedelta

import duckdb
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

DUCK_PATH = os.getenv("DB_PATH", "data/analytics.db")
PG_USER = os.getenv("POSTGRES_USER", "user")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "password")
PG_DB = os.getenv("POSTGRES_DB", "streampulse_meta")
PG_HOST = os.getenv("POSTGRES_HOST", "postgres")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_URL = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

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
        query = """
            SELECT platform, category_name, viewers, top_streamers_detail, ts_utc
            FROM (
                SELECT *,
                    DENSE_RANK() OVER (PARTITION BY platform ORDER BY ts_utc DESC) as rnk
                FROM traffic_category_snapshot
            ) sub
            WHERE rnk = 1
            ORDER BY viewers DESC
        """
        df = con.execute(query).df()
        if not df.empty:
            df["top_streamers_detail"] = df["top_streamers_detail"].apply(_parse_top_streamers)
        return _df_to_records(df)
    finally:
        con.close()

def get_trend_data(category_name, hours=12):
    con = _get_connection()
    try:
        query = f"""
            SELECT ts_utc, platform, viewers, top_streamers_detail
            FROM traffic_category_snapshot
            WHERE category_name = '{category_name}'
              AND ts_utc >= CAST('{datetime.utcnow() - timedelta(hours=hours)}' AS TIMESTAMP)
            ORDER BY ts_utc ASC
        """
        df = con.execute(query).df()
        if not df.empty:
            df["top_streamers_detail"] = df["top_streamers_detail"].apply(_parse_top_streamers)
        return _df_to_records(df)
    finally:
        con.close()

def get_events():
    try:
        engine = create_engine(PG_URL)
        query = "SELECT * FROM signal_events ORDER BY created_at DESC LIMIT 20"
        df = pd.read_sql(query, engine)
        return _df_to_records(df)
    except Exception:
        return []

def get_flash_categories():
    con = _get_connection()
    try:
        ts_check = con.execute("SELECT MAX(ts_utc) FROM traffic_category_snapshot").fetchone()
        if not ts_check or not ts_check[0]:
            return []
        last_ts = ts_check[0]
        query = f"""
            WITH stats AS (
                SELECT
                    platform, category_name,
                    MAX(viewers) as peak_viewers,
                    ARG_MAX(top_streamers_detail, viewers) as peak_streamer_json,
                    COUNT(DISTINCT CAST(ts_utc AS DATE)) FILTER (WHERE viewers > 1000) as active_days
                FROM traffic_category_snapshot
                WHERE ts_utc >= CAST('{datetime.utcnow() - timedelta(days=30)}' AS TIMESTAMP)
                GROUP BY platform, category_name
            ),
            current_status AS (
                SELECT platform, category_name, viewers as curr_viewers, top_streamers_detail as curr_streamer_json
                FROM traffic_category_snapshot
                WHERE ts_utc = CAST('{last_ts}' AS TIMESTAMP)
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
        df = con.execute(query).df()
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

def get_daily_category_top():
    con = _get_connection()
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        query = f"""
            SELECT platform, category_name,
                   CAST(AVG(viewers) AS INT) as avg_viewers,
                   MAX(viewers) as peak_viewers
            FROM traffic_category_snapshot
            WHERE ts_utc >= CAST('{yesterday}' AS TIMESTAMP)
            GROUP BY platform, category_name
            ORDER BY avg_viewers DESC
        """
        df = con.execute(query).df()
        return _df_to_records(df)
    finally:
        con.close()

def get_king_of_streamers():
    con = _get_connection()
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        query = f"""
            SELECT platform, category_name, top_streamers_detail, ts_utc
            FROM traffic_category_snapshot
            WHERE ts_utc >= CAST('{yesterday}' AS TIMESTAMP)
        """
        df_raw = con.execute(query).df()

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

def get_volatility_metrics():
    con = _get_connection()
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        query = f"""
            SELECT platform, category_name,
                   CAST(AVG(viewers) AS INT) as avg_v,
                   (STDDEV(viewers) / NULLIF(AVG(viewers),0)) as volatility_index
            FROM traffic_category_snapshot
            WHERE ts_utc >= CAST('{yesterday}' AS TIMESTAMP)
            GROUP BY 1, 2
            HAVING avg_v > 500
        """
        df = con.execute(query).df()
        return _df_to_records(df)
    finally:
        con.close()
