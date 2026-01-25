import json
import hashlib
import os
import re
from datetime import datetime
from typing import TypedDict, List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from src.agent.cache import get_redis_client
from src.agent.tools import get_search_tool

class AgentState(TypedDict, total=False):
    event_id: int
    platform: str
    category: str
    event_type: str
    signal_level: str
    stats: Dict[str, Any]
    top_clues: List[Dict[str, Any]]
    market: Dict[str, Any]
    category_type: str
    entity_keywords: List[str]
    event_keywords: List[str]
    search_keywords: List[str]
    spike_reason: str
    needs_research: bool
    search_results: str
    final_report: str
    cache_key: str
    cache_hit: bool
    analysis_tier: str
    analysis_verdict: str
    evidence_keywords: List[str]
    analysis_reason: str
    event_kind: str
    watcher_output: Dict[str, Any]
    search_queries: List[str]
    analyst_output: str
    editor_output: str

llm_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0)
llm_pro = ChatOpenAI(model="gpt-4o", temperature=0)
search_tool = get_search_tool()
redis_client = get_redis_client()

def _safe_json_load(text: str):
    if not text:
        return {}
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return {}
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.S)
    if fence:
        cleaned = fence.group(1).strip()
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    try:
        return json.loads(cleaned)
    except Exception:
        return {}

def _normalize_keywords(items, limit=4):
    cleaned = []
    seen = set()
    for kw in items or []:
        if not kw:
            continue
        kw = kw.replace("#", "").strip()
        kw = re.sub(r"\s+", " ", kw)
        if not kw or kw in seen:
            continue
        cleaned.append(kw)
        seen.add(kw)
        if len(cleaned) >= limit:
            break
    return cleaned

def _time_bucket(hours: int = 2):
    now = datetime.utcnow()
    bucket_hour = (now.hour // hours) * hours
    return f"{now:%Y%m%d}{bucket_hour:02d}"

def node_watcher(state: AgentState):
    """[Watcher] 분류/카테고리 보정/핵심 키워드 추출"""
    category = state.get("category") or "-"
    platform = state.get("platform") or "-"
    event_type = state.get("event_type") or "-"
    signal_level = state.get("signal_level") or ""
    stats = state.get("stats") or {}
    clues = state.get("top_clues") or []
    top = clues[0] if clues else {}
    title = top.get("title", "")
    name = top.get("name", "")

    prompt = f"""
    당신은 사건의 실체와 맥락을 파악하는 분석관(Watcher)입니다.
    우리는 2026년 1월 현재 스트리밍 플랫폼(Soop, Chzzk)에서 발생하는 급등 현상을 모니터링하고 있습니다.

    아래 정보를 보고 JSON으로 답하세요.

    [입력]
    플랫폼: {platform}
    카테고리: {category}
    이벤트 타입: {event_type}
    현재/기준/증가: {stats}
    스트리머: {name}
    방송 제목: {title}

    [요청]
    1) category_type: 아래 중 하나로 분류
       - GAME / TALK / SPORTS / MUSIC / IRL / EDUCATION / CREATIVE / NEWS / PLATFORM / OTHER
    2) entity_keywords: 방송 제목/카테고리에서 핵심 고유명사 1~3개 추출
       - 비어있으면 제목에서 1~2개 키워드를 반드시 생성
    3) event_keywords: category_type에 맞는 사건성 키워드 2~4개 생성
       - GAME: 패치, 업데이트, 대회, 이벤트, 시즌, 서버, 점검
       - TALK: 합방, 복귀, 논란, 폭로, 인터뷰, 특별방송
       - SPORTS: 경기, 중계, 선발, 이적, 순위, 결승
       - MUSIC: 컴백, 신곡, 콘서트, 콜라보, 쇼케이스
       - IRL: 여행, 합동, 특집, 현장, 라이브
       - NEWS/PLATFORM: 장애, 점검, 이슈, 공지
    4) search_keywords: 실제 검색에 쓸 키워드 2~4개
       - entity_keywords + event_keywords를 섞어서 구성
       - 예: "봉준", "롤", "패치"
    5) spike_reason: 반드시 "[핵심엔티티] 사건 요약" 형식으로 1문장
    6) needs_research: 외부 검색이 필요한가? (true/false)
    7) category_override: 카테고리 공백/미분류로 판단되면 추론 카테고리, 아니면 null

    [출력 형식]
    - JSON만 출력 (코드블록 금지)

    [출력 JSON 예시]
    {{
      "category_type": "GAME",
      "entity_keywords": ["CES 2026", "라스베가스"],
      "event_keywords": ["행사", "신작", "발표"],
      "search_keywords": ["CES 2026", "라스베가스", "신작 발표"],
      "spike_reason": "[CES 2026] 현장 행사/신작 발표 맥락",
      "needs_research": true,
      "category_override": null
    }}
    """

    response = llm_mini.invoke([HumanMessage(content=prompt)])
    parsed = _safe_json_load(response.content)

    category_type = (parsed.get("category_type") or "OTHER").upper()
    entity_keywords = _normalize_keywords(parsed.get("entity_keywords"), limit=3)
    event_keywords = _normalize_keywords(parsed.get("event_keywords"), limit=4)
    search_keywords = _normalize_keywords(parsed.get("search_keywords"), limit=4)
    spike_reason = parsed.get("spike_reason") or ""
    needs_research = bool(parsed.get("needs_research"))
    actual_delta = int(stats.get("delta") or 0)

    if event_type == "CATEGORY_ADOPTION":
        needs_research = False
    elif event_type == "MARKET_SPIKE" or signal_level == "CANDIDATE":
        needs_research = True
    elif actual_delta >= 10000:
        needs_research = True

    if not entity_keywords:
        fallback = " ".join(part for part in [name, category, title] if part).strip()
        if fallback:
            entity_keywords = _normalize_keywords([fallback.split()[0]], limit=1)

    if not event_keywords:
        default_by_type = {
            "GAME": ["패치", "업데이트", "대회"],
            "TALK": ["합방", "복귀", "논란"],
            "SPORTS": ["경기", "중계", "선발"],
            "MUSIC": ["컴백", "신곡", "콘서트"],
            "IRL": ["합동", "특집", "라이브"],
            "NEWS": ["이슈", "속보", "발표"],
            "PLATFORM": ["점검", "장애", "공지"],
            "OTHER": ["이슈", "공지"],
        }
        event_keywords = default_by_type.get(category_type, ["이슈", "공지"])

    if not search_keywords:
        merged = []
        merged.extend(entity_keywords[:2])
        merged.extend(event_keywords[:2])
        if category:
            merged.append(category)
        search_keywords = _normalize_keywords(merged, limit=4)

    key_base = entity_keywords[0] if entity_keywords else category
    streamer_key = name or "unknown"
    title_key = title or ""
    title_hash = hashlib.sha1(title_key.encode("utf-8")).hexdigest()[:10] if title_key else "no-title"
    cache_key = f"spike:{platform}:{key_base}:{streamer_key}:{title_hash}:{_time_bucket()}"

    if not spike_reason and entity_keywords:
        spike_reason = f"[{entity_keywords[0]}] 관련 이슈"

    watcher_output = {
        "category_type": category_type,
        "entity_keywords": entity_keywords,
        "event_keywords": event_keywords,
        "search_keywords": search_keywords,
        "spike_reason": spike_reason,
        "needs_research": needs_research,
        "category_override": parsed.get("category_override") or None,
    }

    return {
        "category": parsed.get("category_override") or category,
        "category_type": category_type,
        "entity_keywords": entity_keywords,
        "event_keywords": event_keywords,
        "search_keywords": search_keywords,
        "spike_reason": spike_reason,
        "needs_research": needs_research,
        "cache_key": cache_key,
        "watcher_output": watcher_output,
    }

def node_cache_lookup(state: AgentState):
    if os.getenv("DEBUG_NO_CACHE") == "1":
        return {"cache_hit": False}
    if not redis_client:
        return {"cache_hit": False}
    cache_key = state.get("cache_key")
    if not cache_key:
        return {"cache_hit": False}
    try:
        payload = redis_client.get(cache_key)
        if not payload:
            return {"cache_hit": False}
        cached = _safe_json_load(payload)
        return {
            "cache_hit": True,
            "final_report": cached.get("final_report", ""),
            "spike_reason": cached.get("spike_reason", state.get("spike_reason", "")),
            "entity_keywords": cached.get("entity_keywords", state.get("entity_keywords", [])),
            "analysis_tier": cached.get("analysis_tier", "T2"),
            "analysis_verdict": cached.get("analysis_verdict", ""),
            "event_keywords": cached.get("event_keywords", state.get("event_keywords", [])),
        }
    except Exception:
        return {"cache_hit": False}

def node_searcher(state: AgentState):
    """[Searcher] 외부 검색 수행"""
    platform = state.get("platform") or ""
    category = state.get("category") or ""
    clues = state.get("top_clues") or []
    top = clues[0] if clues else {}
    name = top.get("name", "")
    title = top.get("title", "")
    event_keywords = state.get("event_keywords") or []
    entity_keywords = state.get("entity_keywords") or []
    today = datetime.utcnow().date().isoformat()
    primary_event = event_keywords[0] if event_keywords else ""
    secondary_event = event_keywords[1] if len(event_keywords) > 1 else ""

    platform_sites = {
        "SOOP": ["gall.dcinside.com/mini", "fmkorea.com/afreecatv"],
        "CHZZK": ["gall.dcinside.com/mgallery", "fmkorea.com/ib"],
    }
    sites = platform_sites.get(platform, [])

    queries = []
    market_terms = [category, primary_event, secondary_event, "공식", today]
    market_query = " ".join(term for term in market_terms if term).strip()
    if market_query:
        queries.append(market_query)

    personal_terms = [name, primary_event, title, today]
    personal_query = " ".join(term for term in personal_terms if term).strip()
    if personal_query:
        queries.append(personal_query)

    community_terms = [name or category, primary_event or secondary_event]
    community_query_base = " ".join(term for term in community_terms if term).strip()
    if community_query_base and sites:
        queries.append(f"site:{sites[0]} {community_query_base}")
        if len(queries) < 3 and len(sites) > 1:
            queries.append(f"site:{sites[1]} {community_query_base}")

    if len(queries) < 3:
        fallback_terms = [platform, name or category, entity_keywords[0] if entity_keywords else "", today]
        fallback_query = " ".join(term for term in fallback_terms if term).strip()
        if fallback_query:
            queries.append(fallback_query)

    refined = []
    seen = set()
    for q in queries:
        if q and q not in seen:
            refined.append(q)
            seen.add(q)
        if len(refined) >= 3:
            break

    results = []
    for q in refined:
        try:
            res = search_tool.invoke(q)
            if isinstance(res, dict) and "results" in res:
                items = []
                for item in res.get("results", [])[:3]:
                    title = item.get("title", "")
                    url = item.get("url", "")
                    content = (item.get("content") or "")[:200]
                    items.append(f"- {title} ({url}) {content}")
                results.append(f"Q: {q}\n" + "\n".join(items))
            else:
                text = res if isinstance(res, str) else str(res)
                results.append(f"Q: {q}\nA: {text[:500]}")
        except Exception:
            continue
    return {"search_results": "\n".join(results), "search_queries": refined}

def node_analyst(state: AgentState):
    """[Analyst] 심층 분석"""
    clues = state.get("top_clues") or []
    top = clues[0] if clues else {}
    streamer_info = f"{top.get('name', '-')}: {top.get('title', '-')}"
    today = datetime.utcnow().date().isoformat()
    category_type = state.get("category_type") or "OTHER"
    event_keywords = state.get("event_keywords") or []
    category = state.get("category") or "-"
    prompt = f"""
    우리는 지금 2026년 1월, 스트리밍 플랫폼에서 발생하는 급등 현상을 분석하고 있습니다.
    이미 사건의 실체와 맥락을 파악하는 Watcher 단계를 거쳤고 외부 검색 결과도 확보한 상태입니다.
    스트리밍 트렌드 분석가입니다. 검색 결과를 기반으로 급등 원인을 분석하세요.
    급등 원인은 반드시 스트리머 이름/방송 제목/카테고리와 연관성이 있어야 합니다.
    단, 급등 원인은 반드시 존재하는 것이 아닙니다.
    근거가 부족한 경우면 "근거 부족",
    조사할 필요가 없는 단순 시청자 상승이라고 판단될 경우는 "단순 시청자 상승"이라고 답하세요.

    [방송 정보]
    {streamer_info}
    카테고리: {category}
    category_type: {category_type}
    event_keywords: {event_keywords}

    [검색 결과]
    {state.get('search_results', '')}

    [지시사항]
    - 현재 날짜: {today}
    - 1년 이상 지난 과거 뉴스는 배경 정보로만 취급하고 원인으로 단정하지 마세요.
    - 동명이인이 있는 경우 반드시 해당 플랫폼의 스트리머로 한정하세요.
    - 검색 결과에 (스트리머 이름/방송 제목/카테고리)와 event_keywords 중 최소 1개가 함께 나타나지 않으면 "INSUFFICIENT" 판정.
    - category_type과 맞지 않는 사건성 키워드는 노이즈로 간주하세요.
    - 추정/소설 금지. 사실 기반으로만 판단하세요.

    [출력 형식]
    - JSON만 출력 (코드블록 금지)

    [출력 JSON 형식]
    {{
      "verdict": "CONFIRMED | NO_EVENT | INSUFFICIENT",
      "event_kind": "패치/합방/경기/복귀/점검 등",
      "evidence_keywords": ["키워드1", "키워드2"],
      "reason": "1~2문장 요약",
      "confidence": 0.0
    }}
    """
    response = llm_pro.invoke([HumanMessage(content=prompt)])
    parsed = _safe_json_load(response.content)
    verdict = (parsed.get("verdict") or "INSUFFICIENT").upper()
    event_kind = parsed.get("event_kind") or ""
    evidence_keywords = _normalize_keywords(parsed.get("evidence_keywords"), limit=5)
    reason = parsed.get("reason") or response.content
    if verdict not in {"CONFIRMED", "NO_EVENT", "INSUFFICIENT"}:
        verdict = "INSUFFICIENT"
    return {
        "final_report": reason,
        "analysis_tier": "T2",
        "analysis_verdict": verdict,
        "analysis_reason": reason,
        "evidence_keywords": evidence_keywords,
        "analyst_output": parsed or response.content,
        "event_kind": event_kind,
    }

def node_editor(state: AgentState):
    """[Editor] 톤 정리 및 짧은 요약"""
    if state.get("final_report"):
        return {"analysis_tier": state.get("analysis_tier", "T2")}
    top = (state.get("top_clues") or [])
    name = top[0].get("name", "") if top else ""
    title = top[0].get("title", "") if top else ""
    category = state.get("category") or "-"
    spike_reason = state.get("spike_reason") or ""

    prompt = f"""
    너는 T1 요약 담당이다. 아래 입력 외에 어떤 추정도 하지 마라.
    반드시 제목/이름에 있는 단어만 사용하고, 사실을 확장하지 않는다.

    [입력]
    스트리머: {name}
    방송 제목: {title}
    카테고리: {category}
    spike_reason(있으면 사용): {spike_reason}

    [출력 규칙]
    1) 첫 문장은 반드시 "[핵심엔티티] 사건 요약" 형식으로 시작한다.
       - spike_reason이 있으면 그대로 사용
       - 없으면 제목을 그대로 넣어 "[방송 제목] 진행 중"으로 작성
    2) 1~2문장만 출력한다.
    3) 추정/해석/의미 부여 금지.
    """
    response = llm_mini.invoke([HumanMessage(content=prompt)])
    return {
        "final_report": response.content,
        "analysis_tier": "T1",
        "editor_output": response.content,
    }

def node_cache_save(state: AgentState):
    if not redis_client:
        return {}
    if state.get("cache_hit"):
        return {}
    cache_key = state.get("cache_key")
    if not cache_key or not state.get("final_report"):
        return {}
    payload = {
        "final_report": state.get("final_report", ""),
        "spike_reason": state.get("spike_reason", ""),
        "entity_keywords": state.get("entity_keywords", []),
        "analysis_tier": state.get("analysis_tier", "T2"),
        "analysis_verdict": state.get("analysis_verdict", ""),
        "event_keywords": state.get("event_keywords", []),
    }
    try:
        redis_client.setex(cache_key, 3 * 60 * 60, json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass
    return {}

def route_after_cache(state: AgentState):
    if state.get("cache_hit"):
        return "end"
    if state.get("needs_research"):
        return "search"
    return "edit"

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("watcher", node_watcher)
    workflow.add_node("cache_lookup", node_cache_lookup)
    workflow.add_node("search", node_searcher)
    workflow.add_node("analyst", node_analyst)
    workflow.add_node("edit", node_editor)
    workflow.add_node("cache_save", node_cache_save)

    workflow.set_entry_point("watcher")
    workflow.add_edge("watcher", "cache_lookup")
    workflow.add_conditional_edges(
        "cache_lookup",
        route_after_cache,
        {"end": END, "search": "search", "edit": "edit"},
    )
    workflow.add_edge("search", "analyst")
    workflow.add_edge("analyst", "edit")
    workflow.add_edge("edit", "cache_save")
    workflow.add_edge("cache_save", END)

    return workflow.compile()

app = build_graph()
