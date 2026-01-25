import duckdb
import os
import json
import time
from typing import List, Dict, Any

def _is_lock_error(e: BaseException) -> bool:
    msg = str(e).lower()
    return "lock" in msg or "could not set lock" in msg or "conflicting lock" in msg

class DuckDBStore:
    def __init__(self):
        self.db_path = os.getenv("DB_PATH", "data/analytics.db")
        self._init_schema()

    def _get_connection(self):
        """DuckDB 연결 객체 반환"""
        return duckdb.connect(self.db_path)

    def _init_schema(self):
        """테이블이 없으면 생성 (V3: 상위 5 상세 정보 컬럼 추가)"""
        con = self._get_connection()
        try:
            con.execute("""
                CREATE TABLE IF NOT EXISTS traffic_category_snapshot (
                    ts_utc TIMESTAMP,
                    platform VARCHAR,
                    category_id VARCHAR,
                    category_name VARCHAR,
                    viewers INTEGER,
                    open_lives INTEGER,
                    top_streamers_detail VARCHAR 
                );
            """)
        finally:
            con.close()

    def save_category_snapshot(self, data: List[Dict[str, Any]]):
        """카테고리 데이터 저장 (JSON 변환 포함). 락 충돌 시 최대 3회 재시도."""
        if not data:
            return

        values = []
        for d in data:
            detail_json = json.dumps(d.get('top_streamers_detail', []), ensure_ascii=False)
            values.append((
                d['ts_utc'],
                d['platform'],
                d['category_id'],
                d['category_name'],
                d['viewers'],
                d['open_lives'],
                detail_json,
            ))

        max_retries = 3
        backoff = 1.0
        last_err = None
        for attempt in range(max_retries):
            con = None
            try:
                con = self._get_connection()
                con.executemany("""
                    INSERT INTO traffic_category_snapshot 
                    (ts_utc, platform, category_id, category_name, viewers, open_lives, top_streamers_detail)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, values)
                print(f"[DuckDB] 스냅샷 {len(data)}건 저장 완료 (Top 5 포함).")
                return
            except Exception as e:
                last_err = e
                if _is_lock_error(e) and attempt < max_retries - 1:
                    time.sleep(backoff * (2**attempt))
                    continue
                print(f"[DuckDB] 저장 실패: {e}")
                raise last_err
            finally:
                if con:
                    try:
                        con.close()
                    except Exception:
                        pass
