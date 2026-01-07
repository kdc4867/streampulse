import os
import time
import requests
from datetime import datetime, timezone
from collections import defaultdict
from typing import List, Dict, Any

OPENAPI_URL = "https://openapi.chzzk.naver.com/open/v1/lives"
HEADERS = {
    "Client-Id": os.environ.get("CHZZK_CLIENT_ID", ""),
    "Client-Secret": os.environ.get("CHZZK_CLIENT_SECRET", ""),
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
}

def get_utc_now():
    """현재 시간을 UTC로 반환"""
    return datetime.now(timezone.utc).replace(microsecond=0)

def fetch_categories() -> List[Dict[str, Any]]:
    """
    CHZZK의 모든 라이브를 수집하여 카테고리별 통계 + 상위 5 스트리머 정보를 반환
    """
    # API 키가 없으면 수집 불가
    if not HEADERS["Client-Id"]:
        print("[CHZZK] ⚠️ Client-ID 없음. 수집 불가.")
        return []

    params = {"size": 20} 
    
    agg_data = defaultdict(lambda: {
        "name": "Unknown", 
        "total_viewers": 0, 
        "lives": 0, 
        "streams": []
    })
    
    next_token = None
    page_count = 0

    print("[CHZZK] 전체 방송 및 상세 정보 수집 시작...")

    while True:
        if next_token:
            params["next"] = next_token

        try:
            # CHZZK 라이브 목록 API
            response = requests.get(OPENAPI_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
            
            js = response.json()
            content = js.get("content", {})
            items = content.get("data", [])
            
            if not items:
                break

            for item in items:
                cat_id = item.get("liveCategory")
                cat_name = item.get("liveCategoryValue", "기타")
                viewers = item.get("concurrentUserCount", 0)
                
                if not cat_id:
                    cat_id = "ETC"

                group = agg_data[cat_id]
                group["name"] = cat_name
                group["total_viewers"] += viewers
                group["lives"] += 1
                
                channel_info = item.get("channel", {})
                group["streams"].append({
                    "id": item.get("channelId") or channel_info.get("channelId"),
                    "name": item.get("channelName") or channel_info.get("channelName", "Unknown"),
                    "title": item.get("liveTitle", ""),
                    "viewers": viewers
                })
            
            next_token = content.get("page", {}).get("next")
            if not next_token:
                break
                
            page_count += 1
            # 과도한 호출 방지
            time.sleep(0.05)

        except Exception as e:
            print(f"[CHZZK] 수집 중 에러 발생 (Page {page_count}): {e}")
            break
    
    results = []
    ts = get_utc_now()
    
    for cat_id, data in agg_data.items():
        top_5 = sorted(data["streams"], key=lambda x: x["viewers"], reverse=True)[:5]
        
        results.append({
            "ts_utc": ts,
            "platform": "CHZZK",
            "category_id": str(cat_id),
            "category_name": str(data["name"]),
            "viewers": int(data["total_viewers"]),
            "open_lives": int(data["lives"]),
            "top_streamers_detail": top_5
        })
        
    print(f"[CHZZK] 수집 완료. 총 {len(results)}개 카테고리.")
    return results
