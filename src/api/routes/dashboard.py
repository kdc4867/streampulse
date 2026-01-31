from typing import Optional

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
def get_events(
    since: Optional[str] = Query(None, description="YYYY-MM-DD, filter from this date"),
    limit: Optional[int] = Query(None, ge=1, le=500, description="Max rows when since is set"),
):
    try:
        return {"data": service.get_events(since=since, limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trend")
def get_trend(
    category: str = Query(...),
    hours: int = Query(12, ge=1, le=720),
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    try:
        return {"data": service.get_trend_data(category, hours=hours, start=start, end=end)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/flash")
def get_flash(
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    try:
        return {"data": service.get_flash_categories(start=start, end=end)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/daily-top")
def get_daily_top(
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    try:
        return {"data": service.get_daily_category_top(start=start, end=end)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/king")
def get_king(
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    try:
        return {"data": service.get_king_of_streamers(start=start, end=end)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/new")
def get_new():
    try:
        return {"data": service.get_new_categories()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/volatility")
def get_volatility(
    start: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    try:
        return {"data": service.get_volatility_metrics(start=start, end=end)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights-period")
def get_insights_period(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
):
    try:
        return {"data": service.get_insights_period(start=start, end=end)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
