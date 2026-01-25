import duckdb
import json
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

DB_PATH = "data/analytics.db"

def inspect_data():
    try:
        con = duckdb.connect(DB_PATH, read_only=True)

        tables= con.execute("SHOW TABLES;").fetchall()
        print(f" 테이블 목록 : {tables}")

        if not tables:
            print("테이블이 아직 생성되지 않았습니다.")
            return
        
        query = """
            SELECT 
                ts_utc,
                platform,
                category_name,
                viewers,
                top_streamers_detail
            FROM traffic_category_snapshot
            ORDER BY ts_utc DESC
            LIMIT 3
        """
        df = con.execute(query).df()

        print("\n[최신 데이터 샘플]")
        print(df[['ts_utc', 'platform', 'category_name', 'viewers']])

        print("\n[Top 5 상세 정보 검증]")
        for index, row in df.iterrows():
            raw_json = row['top_streamers_detail']
            print(f"\n-- {row['platform']} / {row['category_name']} ({row['viewers']}명) ---")

            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    print(json.dumps(parsed[:2], indent=2, ensure_ascii=False))
                    if len(parsed) > 2:
                        print(f"... 외 {len(parsed)-2}명 더 있음")
                except Exception as e:
                    print(f"JSON 파싱 실패: {e}")
            else:
                print("상세 정보 없음 (NULL or Empty)")
        
        con.close()
    
    except Exception as e:
        print(f" 에러 발생: {e}")
if __name__ == "__main__":
    inspect_data()


        