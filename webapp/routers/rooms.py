"""
webapp/routers/rooms.py

방 관련 API 라우터.
FastAPI 메인 앱에서 include_router 로 붙여 사용할 수 있도록 분리된 모듈입니다.
"""

from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from bot.database import get_db, Room, User, RoomJoin

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


@router.get("", response_model=list[dict])
def list_rooms(db: Session = Depends(get_db)) -> List[dict]:
    """활성 방 목록 반환."""
    rooms = (
        db.query(Room)
        .filter(Room.status == "active")
        .order_by(Room.id.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "room_name": r.room_name,
            "room_url": r.room_url,
            "blinds": r.blinds,
            "min_buyin": r.min_buyin,
            "game_time": r.game_time,
            "description": r.description,
            "status": r.status,
            "current_players": r.current_players,
            "max_players": r.max_players,
        }
        for r in rooms
    ]


@router.get("/{room_id}", response_model=dict)
def get_room(room_id: int, db: Session = Depends(get_db)) -> dict:
    """특정 방 정보 반환."""
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {
        "id": room.id,
        "room_name": room.room_name,
        "room_url": room.room_url,
        "blinds": room.blinds,
        "min_buyin": room.min_buyin,
        "game_time": room.game_time,
        "description": room.description,
        "status": room.status,
        "current_players": room.current_players,
        "max_players": room.max_players,
    }


@router.post("/{room_id}/join", response_model=dict)
def join_room(
    room_id: int,
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    방 참여 기록 생성.
    - 미니앱에서 "게임 참여하기" 버튼 클릭 시 호출.
    """
    room = db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    user = db.get(User, user_id)
    if not user:
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
            created_at=datetime.utcnow(),
        )
        db.add(user)

    user.join_count += 1
    user.last_played = datetime.utcnow()

    join = RoomJoin(user_id=user.user_id, room_id=room.id, joined_at=datetime.utcnow())
    db.add(join)

    db.commit()

    return {"ok": True, "message": "join recorded"}



