"""
bot/handlers/admin.py

관리자용 명령어 핸들러 모듈.
- /admin 명령어 처리
- 방 생성/수정/삭제 등 관리자 기능
- ConversationHandler를 사용한 단계별 입력 처리
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from ..database import SessionLocal, Room
from ..utils import is_admin, ADMIN_IDS

logger = logging.getLogger(__name__)

# Conversation 상태 정의 (방 생성 플로우)
(
    ROOM_NAME,
    ROOM_URL,
    BLINDS,
    MIN_BUYIN,
    GAME_TIME,
    DESCRIPTION,
) = range(6)


async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /admin 명령어 핸들러 - 관리자 메뉴 표시.
    """
    user = update.effective_user
    if not user:
        await update.message.reply_text("사용자 정보를 가져올 수 없습니다.")
        return

    logger.info("명령어 실행: /admin, 사용자: %s", user.id)
    print(f"[CMD] /admin from {user.id}")

    if not ADMIN_IDS:
        await update.message.reply_text(
            "ADMIN_IDS 가 설정되지 않았습니다. .env 의 ADMIN_IDS 를 확인하세요."
        )
        return

    if not is_admin(user.id):
        await update.message.reply_text("이 명령어는 관리자만 사용할 수 있습니다.")
        return

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📝 방 생성", callback_data="admin_create_room"),
                InlineKeyboardButton("✏️ 방 수정", callback_data="admin_update_room"),
            ],
            [
                InlineKeyboardButton("🗑️ 방 삭제", callback_data="admin_delete_room"),
            ],
            [
                InlineKeyboardButton("📊 통계 보기", callback_data="admin_stats"),
                InlineKeyboardButton("📢 공지사항 발송", callback_data="admin_broadcast"),
            ],
        ]
    )

    text = "📌 관리자 메뉴입니다. 원하는 작업을 선택하세요."
    await update.message.reply_text(text, reply_markup=keyboard)


# ==============================
# 방 생성 ConversationHandler
# ==============================


async def admin_create_room_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    방 생성 플로우 시작 (콜백 쿼리에서 호출).
    """
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    if not user or not is_admin(user.id):
        if query:
            await query.message.reply_text("이 기능은 관리자만 사용할 수 있습니다.")
        return ConversationHandler.END

    # 사용자 데이터 초기화
    context.user_data["room_data"] = {}

    text = (
        "📝 새 포커방 생성\n\n"
        "Step 1/6: 방 이름을 입력해 주세요.\n"
        "예: RN.1 TTPOKER 또는 프리미엄 1번방\n\n"
        "취소하려면 /cancel 를 입력하세요."
    )

    if query:
        await query.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())

    return ROOM_NAME


async def admin_create_room_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: 방 이름 입력."""
    room_name = update.message.text.strip()
    if not room_name:
        await update.message.reply_text("방 이름을 입력해 주세요.")
        return ROOM_NAME

    context.user_data["room_data"]["room_name"] = room_name

    text = (
        "Step 2/6: pokernow.club 방 URL을 입력해 주세요.\n"
        "예: https://www.pokernow.club/games/xxxxxxxx\n\n"
        "취소하려면 /cancel 를 입력하세요."
    )
    await update.message.reply_text(text)

    return ROOM_URL


async def admin_create_room_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: 방 URL 입력."""
    room_url = update.message.text.strip()
    if not room_url.startswith("http"):
        await update.message.reply_text(
            "올바른 URL 형식이 아닙니다. http:// 또는 https:// 로 시작하는 URL을 입력해 주세요."
        )
        return ROOM_URL

    context.user_data["room_data"]["room_url"] = room_url

    text = (
        "Step 3/6: 블라인드를 입력해 주세요.\n"
        "예: 100/200 또는 1만/2만\n\n"
        "취소하려면 /cancel 를 입력하세요."
    )
    await update.message.reply_text(text)

    return BLINDS


async def admin_create_room_blinds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: 블라인드 입력."""
    blinds = update.message.text.strip()
    if not blinds:
        await update.message.reply_text("블라인드를 입력해 주세요.")
        return BLINDS

    context.user_data["room_data"]["blinds"] = blinds

    text = (
        "Step 4/6: 최소 바이인을 입력해 주세요.\n"
        "예: 10,000 또는 1만\n\n"
        "취소하려면 /cancel 를 입력하세요."
    )
    await update.message.reply_text(text)

    return MIN_BUYIN


async def admin_create_room_min_buyin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 4: 최소 바이인 입력."""
    min_buyin = update.message.text.strip()
    if not min_buyin:
        await update.message.reply_text("최소 바이인을 입력해 주세요.")
        return MIN_BUYIN

    context.user_data["room_data"]["min_buyin"] = min_buyin

    text = (
        "Step 5/6: 게임 시간을 입력해 주세요.\n"
        "예: 매일 21:00 또는 2분 매너타임\n\n"
        "취소하려면 /cancel 를 입력하세요."
    )
    await update.message.reply_text(text)

    return GAME_TIME


async def admin_create_room_game_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 5: 게임 시간 입력."""
    game_time = update.message.text.strip()
    if not game_time:
        await update.message.reply_text("게임 시간을 입력해 주세요.")
        return GAME_TIME

    context.user_data["room_data"]["game_time"] = game_time

    text = (
        "Step 6/6: 방 설명을 입력해 주세요. (선택사항)\n"
        "설명이 없으면 '없음' 또는 'skip' 을 입력하세요.\n\n"
        "취소하려면 /cancel 를 입력하세요."
    )
    await update.message.reply_text(text)

    return DESCRIPTION


async def admin_create_room_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 6: 설명 입력 및 DB 저장."""
    description = update.message.text.strip()
    if description.lower() in ["없음", "skip", "스킵", "-"]:
        description = None

    room_data: Dict[str, str] = context.user_data.get("room_data", {})

    # 필수 필드 확인
    required_fields = ["room_name", "room_url", "blinds", "min_buyin", "game_time"]
    missing_fields = [f for f in required_fields if f not in room_data]

    if missing_fields:
        await update.message.reply_text(
            f"오류: 필수 정보가 누락되었습니다: {', '.join(missing_fields)}\n"
            "방 생성을 취소합니다."
        )
        context.user_data.pop("room_data", None)
        return ConversationHandler.END

    # DB에 저장
    db = SessionLocal()
    try:
        room = Room(
            room_name=room_data["room_name"],
            room_url=room_data["room_url"],
            blinds=room_data["blinds"],
            min_buyin=room_data["min_buyin"],
            game_time=room_data["game_time"],
            description=description,
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(room)
        db.commit()
        db.refresh(room)

        # 성공 메시지
        success_text = (
            "✅ 새 포커방이 생성되었습니다!\n\n"
            f"📝 방 이름: {room.room_name}\n"
            f"🔗 URL: {room.room_url}\n"
            f"🪙 블라인드: {room.blinds}\n"
            f"💰 최소 바이인: {room.min_buyin}\n"
            f"⏱️ 게임 시간: {room.game_time}\n"
            f"📄 설명: {room.description or '없음'}\n"
            f"🆔 방 ID: {room.id}\n\n"
            "관리자 메뉴로 돌아가려면 /admin 을 입력하세요."
        )

        await update.message.reply_text(success_text)

        logger.info(
            "방 생성 완료: room_id=%s, room_name=%s, user_id=%s",
            room.id,
            room.room_name,
            update.effective_user.id,
        )
        print(f"[ADMIN] Room created: id={room.id}, name={room.room_name}")

    except Exception as e:
        logger.error("방 생성 중 오류 발생: %s", e, exc_info=True)
        print(f"[ERROR] Failed to create room: {e}")
        await update.message.reply_text(
            "❌ 방 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        )
    finally:
        db.close()
        context.user_data.pop("room_data", None)

    return ConversationHandler.END


async def admin_create_room_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """방 생성 취소."""
    context.user_data.pop("room_data", None)
    await update.message.reply_text(
        "❌ 방 생성이 취소되었습니다.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ==============================
# 기타 관리자 콜백 핸들러
# ==============================


async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    관리자 메뉴 콜백 쿼리 처리.
    - admin_create_room: 방 생성 시작
    - admin_update_room, admin_delete_room, admin_stats, admin_broadcast: TODO
    """
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user = query.from_user
    if not is_admin(user.id):
        await query.message.reply_text("이 기능은 관리자만 사용할 수 있습니다.")
        return

    data = query.data

    if data == "admin_create_room":
        # ConversationHandler가 처리하므로 여기서는 아무것도 안 함
        # (실제로는 ConversationHandler의 entry_points에서 처리됨)
        pass
    elif data == "admin_update_room":
        await query.message.reply_text("✏️ 방 수정 기능은 아직 구현 준비 중입니다. (TODO)")
    elif data == "admin_delete_room":
        await query.message.reply_text("🗑️ 방 삭제 기능은 아직 구현 준비 중입니다. (TODO)")
    elif data == "admin_stats":
        # 간단한 통계 예시
        db = SessionLocal()
        try:
            total_rooms = db.query(Room).count()
            active_rooms = db.query(Room).filter(Room.status == "active").count()
            text = (
                "📊 간단 통계\n\n"
                f"- 총 방 수: {total_rooms}\n"
                f"- 활성 방 수: {active_rooms}\n"
            )
            await query.message.reply_text(text)
        finally:
            db.close()
    elif data == "admin_broadcast":
        await query.message.reply_text("📢 공지사항 발송 기능은 아직 구현 준비 중입니다. (TODO)")


# ==============================
# ConversationHandler 빌더
# ==============================


def build_admin_create_room_conversation() -> ConversationHandler:
    """
    방 생성용 ConversationHandler 인스턴스 생성.
    """
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_create_room_start, pattern="^admin_create_room$")
        ],
        states={
            ROOM_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_name)
            ],
            ROOM_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_url)
            ],
            BLINDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_blinds)
            ],
            MIN_BUYIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_min_buyin)
            ],
            GAME_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_game_time)
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_description)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin_create_room_cancel),
            MessageHandler(filters.COMMAND, admin_create_room_cancel),
        ],
    )

