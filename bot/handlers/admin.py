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

from ..database import SessionLocal, Room, Banner
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

# 배너 생성 플로우 상태 (ROOM_* 이후부터 번호 사용)
(
    BANNER_IMAGE_URL,
    BANNER_TITLE,
    BANNER_DESC,
    BANNER_LINK,
    BANNER_ORDER,
) = range(6, 11)


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
                InlineKeyboardButton("🎨 배너 관리", callback_data="admin_banner"),
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
# 배너 생성 ConversationHandler
# ==============================


async def banner_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    새 배너 추가 플로우 시작.
    admin_banner 서브메뉴의 '➕ 새 배너 추가' 버튼에서 진입.
    """
    query = update.callback_query
    if query:
        await query.answer()

    user = update.effective_user
    if not user or not is_admin(user.id):
        if query:
            await query.message.reply_text("이 기능은 관리자만 사용할 수 있습니다.")
        return ConversationHandler.END

    context.user_data["banner_data"] = {}

    text = (
        "🎨 새 배너 추가\n\n"
        "Step 1/5: 배너 이미지 URL을 입력해 주세요.\n"
        "예: https://example.com/banner1.jpg\n\n"
        "취소하려면 /cancel 을 입력하세요."
    )
    if query:
        await query.message.reply_text(text, reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())

    return BANNER_IMAGE_URL


async def banner_add_image_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: 이미지 URL 입력."""
    url = update.message.text.strip()
    if not url.startswith("http"):
        await update.message.reply_text(
            "올바른 URL 형식이 아닙니다. http:// 또는 https:// 로 시작하는 이미지 URL을 입력해 주세요."
        )
        return BANNER_IMAGE_URL

    context.user_data["banner_data"]["image_url"] = url

    text = (
        "Step 2/5: 배너 제목을 입력해 주세요. (선택)\n"
        "제목이 필요 없다면 '없음' 또는 'skip' 을 입력하세요."
    )
    await update.message.reply_text(text)
    return BANNER_TITLE


async def banner_add_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: 제목 입력."""
    title = update.message.text.strip()
    if title.lower() in ["없음", "skip", "스킵", "-"]:
        title = None
    context.user_data["banner_data"]["title"] = title

    text = (
        "Step 3/5: 배너 설명을 입력해 주세요. (선택)\n"
        "설명이 필요 없다면 '없음' 또는 'skip' 을 입력하세요."
    )
    await update.message.reply_text(text)
    return BANNER_DESC


async def banner_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: 설명 입력."""
    desc = update.message.text.strip()
    if desc.lower() in ["없음", "skip", "스킵", "-"]:
        desc = None
    context.user_data["banner_data"]["description"] = desc

    text = (
        "Step 4/5: 배너를 클릭했을 때 이동할 링크 URL을 입력해 주세요. (선택)\n"
        "링크가 필요 없다면 '없음' 또는 'skip' 을 입력하세요."
    )
    await update.message.reply_text(text)
    return BANNER_LINK


async def banner_add_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 4: 링크 URL 입력."""
    link = update.message.text.strip()
    if link.lower() in ["없음", "skip", "스킵", "-"] or not link:
        link = None
    elif not link.startswith("http"):
        await update.message.reply_text(
            "올바른 URL 형식이 아닙니다. http:// 또는 https:// 로 시작하는 링크 URL을 입력해 주세요."
        )
        return BANNER_LINK

    context.user_data["banner_data"]["link_url"] = link

    text = (
        "Step 5/5: 배너 표시 순서 번호를 입력해 주세요. (숫자, 기본값 0)\n"
        "숫자를 입력하지 않으면 0 으로 처리됩니다."
    )
    await update.message.reply_text(text)
    return BANNER_ORDER


async def banner_add_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 5: 순서 번호 입력 및 DB 저장."""
    order_text = update.message.text.strip()
    try:
        order_num = int(order_text)
    except ValueError:
        order_num = 0

    banner_data: Dict[str, str] = context.user_data.get("banner_data", {})
    image_url = banner_data.get("image_url")
    if not image_url:
        await update.message.reply_text(
            "이미지 URL 이 누락되었습니다. 처음부터 다시 시도해 주세요."
        )
        context.user_data.pop("banner_data", None)
        return ConversationHandler.END

    db = SessionLocal()
    try:
        banner = Banner(
            image_url=image_url,
            title=banner_data.get("title"),
            description=banner_data.get("description"),
            link_url=banner_data.get("link_url"),
            order_num=order_num,
            status="active",
            created_at=datetime.utcnow(),
        )
        db.add(banner)
        db.commit()
        db.refresh(banner)

        text = (
            "✅ 새 배너가 등록되었습니다.\n\n"
            f"🖼 이미지 URL: {banner.image_url}\n"
            f"📝 제목: {banner.title or '없음'}\n"
            f"📄 설명: {banner.description or '없음'}\n"
            f"🔗 링크: {banner.link_url or '없음'}\n"
            f"#️⃣ 순서: {banner.order_num}\n"
            f"🆔 배너 ID: {banner.id}\n\n"
            "배너 목록을 보려면 '📋 배너 목록' 버튼을 눌러 주세요."
        )
        await update.message.reply_text(text)

        logger.info(
            "배너 생성 완료: banner_id=%s, image_url=%s, user_id=%s",
            banner.id,
            banner.image_url,
            update.effective_user.id,
        )
        print(f"[ADMIN] Banner created: id={banner.id}, image={banner.image_url}")
    except Exception as e:
        logger.error("배너 생성 중 오류 발생: %s", e, exc_info=True)
        print(f"[ERROR] Failed to create banner: {e}")
        await update.message.reply_text(
            "❌ 배너 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        )
    finally:
        db.close()
        context.user_data.pop("banner_data", None)

    return ConversationHandler.END


async def banner_add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """배너 생성 취소."""
    context.user_data.pop("banner_data", None)
    await update.message.reply_text(
        "❌ 배너 생성이 취소되었습니다.",
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
    - admin_banner*: 배너 관리
    - 기타 admin_*: 통계, 공지 등
    """
    query = update.callback_query
    if not query:
        return

    await query.answer()

    user = query.from_user
    if not is_admin(user.id):
        await query.message.reply_text("이 기능은 관리자만 사용할 수 없습니다.")
        return

    data = query.data or ""

    if data == "admin_create_room":
        # ConversationHandler가 처리하므로 여기서는 아무것도 안 함
        return

    # ===== 배너 관리 서브메뉴 =====
    if data == "admin_banner":
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ 새 배너 추가", callback_data="admin_banner_add")],
                [InlineKeyboardButton("📋 배너 목록", callback_data="admin_banner_list")],
            ]
        )
        await query.message.reply_text("🎨 배너 관리 메뉴입니다.", reply_markup=keyboard)
        return

    if data == "admin_banner_add":
        # ConversationHandler가 처리
        return

    if data == "admin_banner_list":
        # 배너 목록 표시
        db = SessionLocal()
        try:
            banners = (
                db.query(Banner)
                .order_by(Banner.order_num.asc(), Banner.id.asc())
                .all()
            )
            if not banners:
                await query.message.reply_text("등록된 배너가 없습니다.")
                return

            from telegram import InlineKeyboardMarkup, InlineKeyboardButton

            lines = ["📋 등록된 배너 목록:"]
            buttons = []
            for b in banners:
                title = b.title or "(제목 없음)"
                status = b.status
                lines.append(f"#{b.id} - {title} [{status}]")
                buttons.append([
                    InlineKeyboardButton(
                        f"#{b.id} {title[:16]}...",
                        callback_data=f"admin_banner_detail:{b.id}",
                    )
                ])

            await query.message.reply_text("\n".join(lines))
            await query.message.reply_text(
                "자세히 볼 배너를 선택하세요.",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        finally:
            db.close()
        return

    if data.startswith("admin_banner_detail:"):
        # 단일 배너 상세 정보
        try:
            banner_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.message.reply_text("잘못된 배너 ID 입니다.")
            return

        db = SessionLocal()
        try:
            banner = db.get(Banner, banner_id)
            if not banner:
                await query.message.reply_text("해당 배너를 찾을 수 없습니다.")
                return

            from telegram import InlineKeyboardMarkup, InlineKeyboardButton

            text = (
                f"🆔 배너 ID: {banner.id}\n"
                f"🖼 이미지 URL: {banner.image_url}\n"
                f"📝 제목: {banner.title or '없음'}\n"
                f"📄 설명: {banner.description or '없음'}\n"
                f"🔗 링크: {banner.link_url or '없음'}\n"
                f"#️⃣ 순서: {banner.order_num}\n"
                f"상태: {banner.status}\n"
            )
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🗑 배너 삭제", callback_data=f"admin_banner_delete:{banner.id}"
                        ),
                    ],
                ]
            )
            await query.message.reply_text(text, reply_markup=keyboard)
        finally:
            db.close()
        return

    if data.startswith("admin_banner_delete:"):
        # 배너 삭제 처리
        try:
            banner_id = int(data.split(":", 1)[1])
        except ValueError:
            await query.message.reply_text("잘못된 배너 ID 입니다.")
            return

        db = SessionLocal()
        try:
            banner = db.get(Banner, banner_id)
            if not banner:
                await query.message.reply_text("해당 배너를 찾을 수 없습니다.")
                return

            db.delete(banner)
            db.commit()

            await query.message.reply_text(
                f"✅ 배너가 삭제되었습니다. (ID: {banner_id})\n📋 /admin → 🎨 배너 관리 → 📋 배너 목록 에서 다시 확인해 주세요."
            )
            logger.info("배너 삭제: banner_id=%s, user_id=%s", banner_id, user.id)
            print(f"[ADMIN] Banner deleted: id={banner_id}")
        except Exception as e:
            logger.error("배너 삭제 중 오류 발생: %s", e, exc_info=True)
            await query.message.reply_text("❌ 배너 삭제 중 오류가 발생했습니다.")
        finally:
            db.close()
        return

    # ===== 기존 방/통계/공지 처리 =====
    if data == "admin_update_room":
        await query.message.reply_text("✏️ 방 수정 기능은 아직 구현 준비 중입니다. (TODO)")
        return

    if data == "admin_delete_room":
        await query.message.reply_text("🗑️ 방 삭제 기능은 아직 구현 준비 중입니다. (TODO)")
        return

    if data == "admin_stats":
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
        return

    if data == "admin_broadcast":
        await query.message.reply_text("📢 공지사항 발송 기능은 아직 구현 준비 중입니다. (TODO)")
        return


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


def build_banner_create_conversation() -> ConversationHandler:
    """배너 생성용 ConversationHandler 인스턴스 생성."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(banner_add_start, pattern="^admin_banner_add$")
        ],
        states={
            BANNER_IMAGE_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, banner_add_image_url)
            ],
            BANNER_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, banner_add_title)
            ],
            BANNER_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, banner_add_desc)
            ],
            BANNER_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, banner_add_link)
            ],
            BANNER_ORDER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, banner_add_order)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", banner_add_cancel),
            MessageHandler(filters.COMMAND, banner_add_cancel),
        ],
    )

