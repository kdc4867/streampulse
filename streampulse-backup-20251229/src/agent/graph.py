import os
import json
import psycopg2
from typing import TypedDict, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END
from src.agent.tools import get_search_tool

PG_DSN = f"host=postgres dbname={os.getenv('POSTGRES_DB', 'streampulse_meta')} user={os.getenv('POSTGRES_USER', 'user')} password={os.getenv('POSTGRES_PASSWORD', 'password')}"

# === 1. 상태 정의 ===
class AgentState(TypedDict):
    platform: str
    category: str
    cause_type: str
    stats: Dict[str, Any]
    top_clues: List[Dict]
    hypotheses: List[str]
    search_results: str
    final_report: str

# === 2. LLM & 도구 설정 ===
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0) # 창의성 0으로 설정 (팩트 중심)
search_tool = get_search_tool()

# === 3. 노드(Node) 정의 ===

def node_hypothesize(state: AgentState):
    """[가설] 방송 제목을 기반으로 구체적인 검색어 생성"""
    clues = state.get('top_clues', [])
    category = state['category']
    
    if not clues:
        return {"hypotheses": [f"{state['platform']} {category} 이슈", f"{category} 업데이트"]}

    # 인물 이슈인 경우 방송 제목이 핵심
    top_streamer = clues[0]
    name = top_streamer.get('name', '')
    title = top_streamer.get('title', '')
    
    # [수정] 검색어가 너무 포괄적이지 않도록 '방송 제목'의 핵심 키워드 추출 유도
    prompt = f"""
    분석 대상: 스트리머 '{name}'
    방송 제목: "{title}"
    카테고리: {category}
    
    위 방송 제목에서 '이벤트명', '대회명', '합방 멤버', '게임 내 특정 활동' 등 핵심 키워드를 파악하여,
    이 방송이 왜 화제가 되고 있는지 검증할 검색 키워드 2개만 생성하세요.
    (예: 룩삼 Xbox Game Pass Relay, 강퀴 섀도우버스 10억빵)
    
    형식: 키워드1, 키워드2
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    keywords = [k.strip() for k in response.content.split(',')]
    return {"hypotheses": keywords}

def node_investigate(state: AgentState):
    """[조사] 검색 수행"""
    keywords = state['hypotheses']
    print(f"🔎 [Agent] 검색: {keywords}")
    
    results = []
    for kw in keywords:
        try:
            # 검색 결과에서 너무 긴 텍스트는 자름
            res = search_tool.invoke(kw)
            results.append(f"Q: {kw}\nA: {res[:500]}") 
        except Exception:
            pass
            
    return {"search_results": "\n".join(results)}

def node_conclude(state: AgentState):
    """[결론] 팩트 기반 요약 (소설 쓰기 금지)"""
    print("📝 [Agent] 리포트 작성 중...")
    
    clues = state.get('top_clues', [])
    streamer_info = f"{clues[0].get('name')} - {clues[0].get('title')}" if clues else "정보 없음"
    
    # [수정] 프롬프트 대폭 강화: 인물 설명 금지, 현상 묘사 집중
    prompt = f"""
    당신은 팩트만 전달하는 AI 분석가입니다. 
    주어진 방송 정보와 검색 결과를 바탕으로 급등 원인을 분석하세요.
    
    [방송 정보]
    {streamer_info}
    
    [검색 결과]
    {state['search_results']}
    
    [지시사항]
    1. 스트리머에 대한 인물 설명(누구인지, 성격이 어떤지 등)은 절대 하지 마세요.
    2. 오직 '지금 방송에서 무엇을 하고 있는지'에만 집중하세요. (예: 대회 참가, 특정 미션 수행, 신작 게임 플레이 등)
    3. 방송 제목에 'Relay', '대회', '합방', '이벤트' 등의 단어가 있다면 그것을 핵심 원인으로 지목하세요.
    4. 검색 결과가 부정확하거나 정보가 없으면, 솔직하게 "특이 이슈 없음. 방송 제목({clues[0].get('title', '')}) 관련 일반적인 시청자 유입으로 보입니다."라고 적으세요.
    5. 없는 사실을 지어내지 마세요. (Hallucination 엄격 금지)
    
    결과는 2문장 이내로 요약하세요.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"final_report": response.content}

def node_save_to_db(state: AgentState):
    """[저장] Evidence 제외하고 Report만 저장"""
    try:
        conn = psycopg2.connect(PG_DSN)
        cur = conn.cursor()
        
        update_query = """
            UPDATE signal_events
            SET cause_detail = cause_detail || %s::jsonb
            WHERE event_id = (
                SELECT event_id FROM signal_events 
                WHERE platform = %s AND category_name = %s 
                ORDER BY created_at DESC LIMIT 1
            )
        """
        
        # [수정] evidence 삭제, ai_report만 깔끔하게 저장
        analysis_data = json.dumps({
            "ai_report": state['final_report']
        })
        
        cur.execute(update_query, (analysis_data, state['platform'], state['category']))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ [Agent] DB 저장 실패: {e}")
        
    return {}

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("hypothesize", node_hypothesize)
    workflow.add_node("investigate", node_investigate)
    workflow.add_node("conclude", node_conclude)
    workflow.add_node("save_result", node_save_to_db)
    
    workflow.set_entry_point("hypothesize")
    workflow.add_edge("hypothesize", "investigate")
    workflow.add_edge("investigate", "conclude")
    workflow.add_edge("conclude", "save_result")
    workflow.add_edge("save_result", END)
    
    return workflow.compile()

app = build_graph()