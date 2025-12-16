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
    try:
        print(f"[API] 쿠폰 조회 시작: user_id={user_id}")
        
        coupons = db.query(Coupon).filter(
            Coupon.user_id == user_id
        ).all()
        
        print(f"[API] 쿠폰 조회: user_id={user_id}, 개수={len(coupons)}")
        
        result = [
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
        
        print(f"[API] 쿠폰 결과: {result}")
        
        return result
    except Exception as e:
        print(f"[API ERROR] 쿠폰 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        raise


@router.get("/coupons", response_class=HTMLResponse)
async def coupons_page(request: Request):
    """쿠폰함 페이지"""
    return templates.TemplateResponse("coupons.html", {"request": request})

