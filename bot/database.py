"""
bot/database.py

FastAPI 웹앱과 텔레그램 봇에서 함께 사용할 SQLite 데이터베이스 모델 정의.

- rooms: 포커방 정보
- users: 유저 통계
- room_joins: 방 참여 로그
- banners: 배너 정보
"""

from __future__ import annotations

from datetime import datetime
from typing import Generator

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
    ForeignKey,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

from dotenv import load_dotenv
import os
from pathlib import Path

# .env 로드 (DATABASE_URL 등이 있으면 사용)
load_dotenv()

# 기본 SQLite URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///poker.db")

# Vercel 환경 여부 감지 (Vercel 은 VERCEL=1 환경변수 설정)
IS_VERCEL = os.getenv("VERCEL") == "1"

if DATABASE_URL.startswith("sqlite:///"):
    raw_path = DATABASE_URL.replace("sqlite:///", "")  # 예: "poker.db" 또는 "some/path.db"

    if IS_VERCEL:
        # Vercel 서버리스의 경우 /tmp 만 쓰기 가능 → /tmp 하위로 강제 설정
        if not raw_path.startswith("/"):
            fixed_path = f"/tmp/{raw_path}"
        else:
            fixed_path = raw_path
        DATABASE_URL = f"sqlite:///{fixed_path}"
    else:
        # 로컬/일반 서버: 프로젝트 루트 기준 경로로 변환
        base_dir = Path(__file__).resolve().parent.parent
        db_path = base_dir / raw_path
        DATABASE_URL = f"sqlite:///{db_path}"

# SQLite 엔진 생성
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Room(Base):
    """포커방 정보 테이블."""

    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_name = Column(String(100), nullable=False)
    room_url = Column(Text, nullable=False)
    blinds = Column(String(50))
    min_buyin = Column(String(50))
    game_time = Column(String(50))
    description = Column(Text)
    status = Column(String(20), default="active")
    current_players = Column(Integer, default=0)
    max_players = Column(Integer, default=9)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    joins = relationship("RoomJoin", back_populates="room")


class User(Base):
    """유저 정보/통계 테이블."""

    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, autoincrement=False)
    username = Column(String(100))
    first_name = Column(String(100))
    join_count = Column(Integer, default=0)
    total_playtime = Column(Integer, default=0)
    last_played = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    joins = relationship("RoomJoin", back_populates="user")


class RoomJoin(Base):
    """방 참여 로그 테이블."""

    __tablename__ = "room_joins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    room_id = Column(Integer, ForeignKey("rooms.id"))
    joined_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="joins")
    room = relationship("Room", back_populates="joins")


class Banner(Base):
    """배너 정보 테이블."""

    __tablename__ = "banners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_url = Column(Text, nullable=False)
    title = Column(String(200))
    description = Column(Text)
    link_url = Column(Text)
    order_num = Column(Integer, default=0)
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    """테이블이 없으면 모두 생성."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 의 Depends, 또는 스크립트/봇에서 사용할 세션 제공 함수.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



