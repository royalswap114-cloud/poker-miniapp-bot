"""
webapp/routers/coupons.py

쿠폰 관련 API 및 페이지 라우터.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path

from bot.database import get_db, Coupon

# 템플릿 디렉토리 경로 설정 (절대 경로)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "webapp" / "templates"

router = APIRouter()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/api/coupons/{user_id}")
async def get_user_coupons(user_id: int, db: Session = Depends(get_db)):
    """사용자 쿠폰 목록 조회 API"""
    coupons = db.query(Coupon).filter(
        Coupon.user_id == user_id
    ).all()
    
    return [
        {
            "id": c.id,
            "code": c.coupon_code,
            "title": c.title,
            "description": c.description,
            "amount": c.discount_amount,
            "is_used": c.is_used,
            "expires_at": c.expires_at.isoformat() if c.expires_at else None
        }
        for c in coupons
    ]


@router.get("/coupons", response_class=HTMLResponse)
async def coupons_page(request: Request):
    """쿠폰함 페이지"""
    return templates.TemplateResponse("coupons.html", {"request": request})

