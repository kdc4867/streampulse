from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

def get_search_tool():
    """
    무료 웹 검색 도구 (DuckDuckGo)
    - 한국어 검색 결과 우선 설정
    """
    wrapper = DuckDuckGoSearchAPIWrapper(region="kr-kr", time="d") # 한국 지역, 하루 이내 결과 우선
    search = DuckDuckGoSearchRun(api_wrapper=wrapper)
    return search