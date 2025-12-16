"""
webapp/routers/events.py

이벤트 관련 API 및 페이지 라우터.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from bot.database import get_db, Event

# 템플릿 디렉토리 경로 설정 (절대 경로)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "webapp" / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/api/events")
async def get_events(db: Session = Depends(get_db)):
    """이벤트 목록 조회"""
    events = db.query(Event).filter(Event.status == "active").order_by(Event.priority.desc(), Event.created_at.desc()).all()
    
    return [
        {
            "id": e.id,
            "title": e.title,
            "content": e.content,
            "image_url": e.image_url,
            "created_at": e.created_at.isoformat()
        }
        for e in events
    ]


@router.get("/events", response_class=HTMLResponse)
async def events_page(request: Request):
    """이벤트 페이지"""
    return templates.TemplateResponse("events.html", {"request": request})

