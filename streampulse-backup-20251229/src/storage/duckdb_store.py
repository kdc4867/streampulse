import duckdb
import os
import json
from typing import List, Dict, Any

class DuckDBStore:
    def __init__(self):
        # 환경변수에서 DB 경로 가져오기 (없으면 기본값)
        self.db_path = os.getenv("DB_PATH", "data/analytics.db")
        self._init_schema()

    def _get_connection(self):
        """DuckDB 연결 객체 반환"""
        return duckdb.connect(self.db_path)

    def _init_schema(self):
        """테이블이 없으면 생성 (V3: Top 5 상세 정보 컬럼 추가)"""
        con = self._get_connection()
        try:
            # 1. 카테고리 스냅샷 테이블
            # top_streamers_detail: JSON Array String (ex: '[{"name":"악어", "title":"...", "viewers":5000}, ...]')
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
            # V3에서는 traffic_streamer_snapshot 테이블을 별도로 쓰지 않고 
            # top_streamers_detail 컬럼에 핵심 정보를 압축 저장하는 방식을 사용합니다.
            
        finally:
            con.close()

    def save_category_snapshot(self, data: List[Dict[str, Any]]):
        """카테고리 데이터 저장 (JSON 변환 포함)"""
        if not data:
            return

        con = self._get_connection()
        try:
            # List[Dict] -> List[Tuple] 변환
            values = []
            for d in data:
                # Top 5 리스트를 JSON 문자열로 변환 (DB 저장용)
                # 수집기에서 'top_streamers_detail' 키에 리스트를 담아 보내야 함
                detail_json = json.dumps(d.get('top_streamers_detail', []), ensure_ascii=False)
                
                values.append((
                    d['ts_utc'], 
                    d['platform'], 
                    d['category_id'], 
                    d['category_name'], 
                    d['viewers'], 
                    d['open_lives'],
                    detail_json
                ))
            
            con.executemany("""
                INSERT INTO traffic_category_snapshot 
                (ts_utc, platform, category_id, category_name, viewers, open_lives, top_streamers_detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, values)
            
            print(f"[DuckDB] 스냅샷 {len(data)}건 저장 완료 (Top 5 포함).")
        except Exception as e:
            print(f"[DuckDB] 저장 실패: {e}")
        finally:
            con.close()