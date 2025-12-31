from fastapi import APIRouter, HTTPException, Query
from src.api.services import dashboard as service

router = APIRouter()

@router.get("/live")
def get_live():
    try:
        return {"data": service.get_live_traffic()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/events")
def get_events():
    try:
        return {"data": service.get_events()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trend")
def get_trend(category: str = Query(...), hours: int = Query(12, ge=1, le=720)):
    try:
        return {"data": service.get_trend_data(category, hours)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flash")
def get_flash():
    try:
        return {"data": service.get_flash_categories()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/daily-top")
def get_daily_top():
    try:
        return {"data": service.get_daily_category_top()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/king")
def get_king():
    try:
        return {"data": service.get_king_of_streamers()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/new")
def get_new():
    try:
        return {"data": service.get_new_categories()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/volatility")
def get_volatility():
    try:
        return {"data": service.get_volatility_metrics()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
