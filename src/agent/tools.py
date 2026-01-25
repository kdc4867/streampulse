import os
from typing import Dict, Any, List

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
import requests
try:
    from langchain_community.tools import TavilySearchResults
except Exception:
    TavilySearchResults = None

class BraveSearch:
    def __init__(self, api_key: str, k: int = 5):
        self.api_key = api_key
        self.k = k

    def invoke(self, query: str) -> Dict[str, Any]:
        if not query:
            return {"results": []}
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query,
            "count": self.k,
            "country": "KR",
            "search_lang": "ko",
            "ui_lang": "ko-KR",
            "freshness": "day",
        }
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return {"results": [], "error": str(exc)}

        items: List[Dict[str, Any]] = []
        for entry in data.get("web", {}).get("results", [])[: self.k]:
            items.append(
                {
                    "title": entry.get("title", ""),
                    "url": entry.get("url", ""),
                    "content": entry.get("description", ""),
                }
            )
        return {"results": items}

def get_search_tool():
    """
    무료 웹 검색 도구 (DuckDuckGo)
    - 한국어 검색 결과 우선 설정
    """
    brave_key = os.getenv("BRAVE_API_KEY")
    if brave_key:
        return BraveSearch(api_key=brave_key, k=5)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key and TavilySearchResults:
        return TavilySearchResults(k=5)
    wrapper = DuckDuckGoSearchAPIWrapper(region="kr-kr", time="d")
    return DuckDuckGoSearchRun(api_wrapper=wrapper)
