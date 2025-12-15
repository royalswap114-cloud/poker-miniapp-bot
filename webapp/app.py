"""
webapp/app.py

FastAPI 기반 텔레그램 WebApp 서버.
- 템플릿(index.html)로 미니앱 UI 제공
- /api/rooms 등 REST API 제공
- CORS 설정 포함 (텔레그램 WebApp 도메인 + localhost 허용)
"""

from __future__ import annotations

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from dotenv import load_dotenv
import os
from pathlib import Path

from bot.database import init_db, get_db, User, Banner
from .routers import rooms as rooms_router

load_dotenv()

WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8000")

# 현재 파일(webapp/app.py) 기준으로 프로젝트 루트 경로 계산
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "webapp" / "templates"
STATIC_DIR = BASE_DIR / "webapp" / "static"

app = FastAPI(title="Poker MiniApp")

# 정적 파일, 템플릿 설정 (절대 경로 사용 - Vercel 등 서버리스 환경에서도 안전)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# CORS 설정
origins = [
    WEBAPP_URL,
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    """애플리케이션 시작 시 DB 초기화."""
    init_db()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """
    미니앱 메인 페이지.
    실제 데이터는 JS(main.js)가 /api/* 를 통해 불러옵니다.
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "webapp_url": WEBAPP_URL,
        },
    )


@app.get("/api/banners")
async def api_get_banners(db: Session = Depends(get_db)) -> list[dict]:
    """활성 배너 목록 반환."""
    banners = (
        db.query(Banner)
        .filter(Banner.status == "active")
        .order_by(Banner.order_num.asc(), Banner.id.asc())
        .all()
    )
    return [
        {
            "id": b.id,
            "image_url": b.image_url,
            "title": b.title,
            "description": b.description,
            "link_url": b.link_url,
        }
        for b in banners
    ]


@app.get("/api/users/{user_id}")
async def api_get_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    """유저 정보 반환 (프로필에서 사용)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "user_id": user.user_id,
        "username": user.username,
        "first_name": user.first_name,
        "join_count": user.join_count,
        "total_playtime": user.total_playtime,
        "last_played": user.last_played,
        "created_at": user.created_at,
    }


# rooms 관련 API 라우터 등록
app.include_router(rooms_router.router)



