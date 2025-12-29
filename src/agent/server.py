from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from src.agent.graph import app as agent_app

app = FastAPI(title="StreamPulse Agent")

# === [수정] 입력 데이터 구조 변경 (Detector V3 대응) ===
class AnalyzeRequest(BaseModel):
    platform: str
    category: str
    cause_type: str        # "PERSON_ISSUE" or "STRUCTURE_ISSUE"
    stats: Dict[str, Any]  # {current, baseline, delta}
    top_clues: List[Dict[str, Any]] # Top 5 스트리머 정보

@app.post("/analyze")
def analyze_trend(req: AnalyzeRequest):
    """에이전트에게 분석을 의뢰하는 API"""
    print(f"🚀 [Agent API] 요청 수신: {req.platform} - {req.category} ({req.cause_type})")
    
    try:
        # LangGraph 실행을 위한 초기 상태값 설정
        inputs = {
            "platform": req.platform,
            "category": req.category,
            "cause_type": req.cause_type, # [New] 원인 유형 전달
            "growth_rate": f"{req.stats.get('growth_ratio', 0)}배 급등", # 그래프 내부 호환용
            "top_clues": req.top_clues,   # [New] 결정적 단서 전달
            "hypotheses": [],
            "search_results": "",
            "final_report": ""
        }
        
        # 아직 graph.py는 수정을 안 했으므로, 
        # 일단 입력을 받아주는 것까지만 성공시켜 둡니다.
        # (제대로 된 분석은 Phase 3에서 graph.py 고칠 때 적용됨)
        result = agent_app.invoke(inputs)
        
        return {
            "status": "success",
            "report": result.get("final_report", "분석 중..."),
            "evidence": result.get("search_results", "")
        }
    except Exception as e:
        print(f"🔥 [Agent Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 실행: uvicorn src.agent.server:app --host 0.0.0.0 --port 8000