from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from src.agent.graph import app as agent_app

app = FastAPI(title="StreamPulse Agent")

class AnalyzeRequest(BaseModel):
    platform: str
    category: str
    cause_type: str        # "PERSON_ISSUE" 또는 "STRUCTURE_ISSUE"
    stats: Dict[str, Any]  # {current, baseline, delta}
    top_clues: List[Dict[str, Any]] # 상위 5 스트리머 정보

@app.post("/analyze")
def analyze_trend(req: AnalyzeRequest):
    """에이전트에게 분석을 의뢰하는 API"""
    print(f"🚀 [Agent API] 요청 수신: {req.platform} - {req.category} ({req.cause_type})")
    
    try:
        inputs = {
            "platform": req.platform,
            "category": req.category,
            "cause_type": req.cause_type,
            "growth_rate": f"{req.stats.get('growth_ratio', 0)}배 급등",
            "top_clues": req.top_clues,
            "hypotheses": [],
            "search_results": "",
            "final_report": ""
        }
        result = agent_app.invoke(inputs)
        
        return {
            "status": "success",
            "report": result.get("final_report", "분석 중..."),
            "evidence": result.get("search_results", "")
        }
    except Exception as e:
        print(f"🔥 [Agent Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))
