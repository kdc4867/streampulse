import time
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any

BASE_URL = "https://sch.sooplive.co.kr/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.sooplive.co.kr/",
}

def get_utc_now():
    """현재 시간을 UTC로 반환 (DB 저장용)"""
    return datetime.now(timezone.utc).replace(microsecond=0)

def fetch_categories() -> List[Dict[str, Any]]:
    """
    SOOP 카테고리 목록 수집 + 상위 카테고리에 한해 상위 5 스트리머 정보 추가 수집
    """
    results = []
    
    category_map = {}
    
    page = 1
    max_pages = 2
    
    while page <= max_pages:
        params = {
            "m": "categoryList",
            "szOrder": "view_cnt",
            "nPageNo": page,
            "nListCnt": 120,
            "szPlatform": "pc",
        }
        try:
            # 카테고리 목록 API
            resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            items = data.get("list", [])
            if not items:
                break

            ts = get_utc_now()
            for item in items:
                cat_no = str(item.get("category_no", ""))
                cat_name = item.get("category_name", "Unknown")
                viewers = int(item.get("view_cnt", 0))
                
                category_obj = {
                    "ts_utc": ts,
                    "platform": "SOOP",
                    "category_id": cat_no,
                    "category_name": cat_name,
                    "viewers": viewers,
                    "open_lives": 0,
                    "top_streamers_detail": []
                }
                results.append(category_obj)
                category_map[cat_no] = category_obj
            
            if not data.get("is_more"):
                break
            page += 1
            time.sleep(0.1)
            
        except Exception as e:
            print(f"[SOOP] 목록 수집 에러: {e}")
            break

    # 상위 카테고리만 상세 조회: 전체 호출은 느리고 차단 위험이 큼
    sorted_cats = sorted(results, key=lambda x: x['viewers'], reverse=True)[:30]
    
    print(f"[SOOP] 상위 {len(sorted_cats)}개 카테고리 상세 정보(Top 5) 수집 중...")
    
    for cat_obj in sorted_cats:
        cat_no = cat_obj['category_id']
        try:
            detail_params = {
                "m": "categoryContentsList",
                "szType": "live",
                "nPageNo": 1,
                "nListCnt": 10,
                "szPlatform": "pc",
                "szOrder": "view_cnt_desc",
                "szCateNo": cat_no,
            }
            # 카테고리별 라이브 목록 API
            resp = requests.get(BASE_URL, params=detail_params, headers=HEADERS, timeout=5)
            d_data = resp.json().get("data", {})
            d_items = d_data.get("list", [])
            
            top_5 = []
            for item in d_items[:5]:
                top_5.append({
                    "id": item.get("user_id"),
                    "name": item.get("user_nick"),
                    "title": item.get("broad_title", ""),
                    "viewers": int(item.get("view_cnt", 0))
                })
            
            cat_obj['top_streamers_detail'] = top_5
            cat_obj['open_lives'] = int(d_data.get("total_cnt", 0))
            
            time.sleep(0.1)
            
        except Exception as e:
            print(f"[SOOP] 상세 수집 실패 ({cat_no}): {e}")
            
    print(f"[SOOP] 수집 완료. 총 {len(results)}개 카테고리.")
    return results
