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

from ..database import SessionLocal, Room, Banner, Coupon, Event, User
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

# 인원 수 업데이트 플로우 상태
ROOM_PLAYERS_INPUT = 11

# 쿠폰 관리 플로우 상태
(
    COUPON_USER_ID,
    COUPON_TITLE,
    COUPON_DESC,
    COUPON_AMOUNT,
    COUPON_EXPIRES,
) = range(200, 205)

# 이벤트 관리 플로우 상태
(
    EVENT_TITLE,
    EVENT_CONTENT,
    EVENT_IMAGE,
) = range(210, 213)


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
                InlineKeyboardButton("🔄 인원 수 업데이트", callback_data="admin_update_players"),
            ],
            [
                InlineKeyboardButton("🎟️ 쿠폰 관리", callback_data="admin_coupons"),
                InlineKeyboardButton("🎉 이벤트 관리", callback_data="admin_events"),
            ],
            [
                InlineKeyboardButton("📊 통계 보기", callback_data="admin_stats"),
                InlineKeyboardButton("🎨 배너 관리", callback_data="admin_banner"),
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

    if data == "admin_menu":
        # 관리자 메뉴로 돌아가기
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
                    InlineKeyboardButton("🔄 인원 수 업데이트", callback_data="admin_update_players"),
                ],
                [
                    InlineKeyboardButton("📊 통계 보기", callback_data="admin_stats"),
                    InlineKeyboardButton("📢 공지사항 발송", callback_data="admin_broadcast"),
                ],
            ]
        )
        
        await query.edit_message_text(
            "📌 관리자 메뉴입니다. 원하는 작업을 선택하세요.",
            reply_markup=keyboard
        )
        return

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

    # ===== 방 관리 =====
    if data == "admin_update_room":
        await admin_edit_room_list(update, context)
        return

    if data == "admin_delete_room":
        await admin_delete_room_list(update, context)
        return

    # delete_room_ 패턴은 별도 핸들러에서 처리 (poker_miniapp_bot.py)

    # ===== 쿠폰 관리 =====
    if data == "admin_coupons":
        await admin_coupons(update, context)
        return

    if data == "admin_create_coupon":
        # ConversationHandler가 처리
        return

    # ===== 이벤트 관리 =====
    if data == "admin_events":
        await admin_events(update, context)
        return

    if data == "admin_create_event":
        # ConversationHandler가 처리
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


    # ===== 인원 수 업데이트 =====
    if data == "admin_update_players":
        await admin_update_players(update, context)
        return

    if data.startswith("update_room_players_"):
        # ConversationHandler가 처리하므로 여기서는 아무것도 안 함
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


# ==============================
# 인원 수 업데이트 ConversationHandler
# ==============================


async def admin_update_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """관리자: 방 인원 수 업데이트 메뉴 표시"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    user = query.from_user
    if not is_admin(user.id):
        await query.message.reply_text("이 기능은 관리자만 사용할 수 없습니다.")
        return
    
    db = SessionLocal()
    
    try:
        rooms = db.query(Room).filter(Room.status == "active").all()
        
        if not rooms:
            await query.edit_message_text("활성화된 방이 없습니다.")
            return
        
        # 각 방의 현재 인원 수 표시
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = []
        for room in rooms:
            button_text = f"{room.room_name} ({room.current_players}/{room.max_players})"
            keyboard.append([InlineKeyboardButton(
                button_text, 
                callback_data=f"update_room_players_{room.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("« 뒤로", callback_data="admin_menu")])
        
        await query.edit_message_text(
            "📊 현재 인원 수를 업데이트할 방을 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Error in admin_update_players: {e}", exc_info=True)
        await query.message.reply_text("❌ 오류가 발생했습니다.")
    finally:
        db.close()


async def update_room_players_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """특정 방의 인원 수 입력 시작"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    try:
        room_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.message.reply_text("잘못된 방 ID입니다.")
        return ConversationHandler.END
    
    context.user_data['updating_room_id'] = room_id
    
    db = SessionLocal()
    
    try:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            await query.edit_message_text("방을 찾을 수 없습니다.")
            return ConversationHandler.END
        
        await query.edit_message_text(
            f"🎮 {room.room_name}\n\n"
            f"현재 인원: {room.current_players}/{room.max_players}\n\n"
            f"새로운 인원 수를 입력하세요 (0-{room.max_players}):\n"
            f"취소하려면 /cancel"
        )
        
        return ROOM_PLAYERS_INPUT
    except Exception as e:
        logger.error(f"Error in update_room_players_start: {e}", exc_info=True)
        await query.message.reply_text("❌ 오류가 발생했습니다.")
        return ConversationHandler.END
    finally:
        db.close()


async def update_room_players_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """방 인원 수 입력 처리"""
    try:
        players = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("숫자를 입력해주세요.")
        return ROOM_PLAYERS_INPUT
    
    room_id = context.user_data.get('updating_room_id')
    if not room_id:
        await update.message.reply_text("오류가 발생했습니다. 다시 시도해주세요.")
        return ConversationHandler.END
    
    db = SessionLocal()
    
    try:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            await update.message.reply_text("방을 찾을 수 없습니다.")
            return ConversationHandler.END
        
        if players < 0 or players > room.max_players:
            await update.message.reply_text(
                f"0부터 {room.max_players} 사이의 숫자를 입력하세요."
            )
            return ROOM_PLAYERS_INPUT
        
        old_players = room.current_players
        room.current_players = players
        db.commit()
        
        await update.message.reply_text(
            f"✅ 업데이트 완료!\n\n"
            f"🎮 {room.room_name}\n"
            f"인원: {old_players} → {players}"
        )
        
        logger.info(f"Room {room.id} players updated: {old_players} → {players}")
        print(f"[ADMIN] Room {room.id} players updated: {old_players} → {players}")
        
    except Exception as e:
        logger.error(f"Error in update_room_players_input: {e}", exc_info=True)
        await update.message.reply_text("❌ 업데이트 중 오류가 발생했습니다.")
        db.rollback()
    finally:
        db.close()
    
    # 사용자 데이터 정리
    context.user_data.pop('updating_room_id', None)
    
    return ConversationHandler.END


async def update_players_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """인원 수 업데이트 취소"""
    context.user_data.pop('updating_room_id', None)
    await update.message.reply_text("인원 수 업데이트가 취소되었습니다.")
    return ConversationHandler.END


def build_update_players_conversation() -> ConversationHandler:
    """인원 수 업데이트용 ConversationHandler 인스턴스 생성."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(update_room_players_start, pattern="^update_room_players_")
        ],
        states={
            ROOM_PLAYERS_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_room_players_input)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", update_players_cancel),
            MessageHandler(filters.COMMAND, update_players_cancel),
        ],
    )


# ==============================
# 방 수정/삭제 기능
# ==============================


async def admin_edit_room_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """방 수정: 방 목록 표시"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    db = SessionLocal()
    
    try:
        rooms = db.query(Room).all()
        
        if not rooms:
            await query.edit_message_text("등록된 방이 없습니다.")
            return
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = []
        for room in rooms:
            keyboard.append([InlineKeyboardButton(
                f"{room.room_name} [{room.status}]",
                callback_data=f"edit_room_{room.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("« 뒤로", callback_data="admin_menu")])
        
        await query.edit_message_text(
            "✏️ 수정할 방을 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        db.close()


async def admin_delete_room_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """방 삭제: 방 목록 표시"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    db = SessionLocal()
    
    try:
        rooms = db.query(Room).all()
        
        if not rooms:
            await query.edit_message_text("등록된 방이 없습니다.")
            return
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = []
        for room in rooms:
            keyboard.append([InlineKeyboardButton(
                f"🗑 {room.room_name}",
                callback_data=f"delete_room_{room.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("« 취소", callback_data="admin_menu")])
        
        await query.edit_message_text(
            "⚠️ 삭제할 방을 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    finally:
        db.close()


async def admin_delete_room_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """방 삭제 실행"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    logger.info(f"[DELETE_ROOM] Called for data: {query.data}")
    print(f"[ADMIN] DELETE_ROOM callback: {query.data}")
    
    try:
        room_id = int(query.data.split("_")[-1])
        logger.info(f"[DELETE_ROOM] Parsed room_id: {room_id}")
    except (ValueError, IndexError) as e:
        logger.error(f"[DELETE_ROOM] Failed to parse room_id: {e}")
        await query.message.reply_text("잘못된 방 ID입니다.")
        return
    
    db = SessionLocal()
    
    try:
        room = db.query(Room).filter(Room.id == room_id).first()
        if not room:
            await query.edit_message_text("방을 찾을 수 없습니다.")
            return
        
        room_name = room.room_name
        db.delete(room)
        db.commit()
        
        logger.info(f"Deleted room: {room_id} ({room_name})")
        print(f"[ADMIN] Room deleted: id={room_id}, name={room_name}")
        
        # 업데이트된 방 목록으로 메뉴 다시 표시
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        rooms = db.query(Room).all()
        keyboard = [
            [InlineKeyboardButton("➕ 새 방 만들기", callback_data="admin_create_room")],
            [InlineKeyboardButton("✏️ 방 수정", callback_data="admin_update_room")],
            [InlineKeyboardButton("🗑 방 삭제", callback_data="admin_delete_room")],
            [InlineKeyboardButton("« 뒤로", callback_data="admin_menu")]
        ]
        
        await query.edit_message_text(
            f"✅ '{room_name}' 방이 삭제되었습니다.\n\n"
            f"🏠 *방 관리*\n\n"
            f"현재 등록된 방: {len(rooms)}개",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Error deleting room: {e}", exc_info=True)
        await query.message.reply_text("❌ 방 삭제 중 오류가 발생했습니다.")
        db.rollback()
    finally:
        db.close()


# ==============================
# 쿠폰 관리 기능
# ==============================


async def admin_coupons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """쿠폰 관리 메뉴"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = [
        [InlineKeyboardButton("➕ 쿠폰 발급", callback_data="admin_create_coupon")],
        [InlineKeyboardButton("📋 쿠폰 목록", callback_data="admin_list_coupons")],
        [InlineKeyboardButton("« 뒤로", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(
        "🎟️ *쿠폰 관리*\n\n"
        "원하는 작업을 선택하세요:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def admin_create_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 발급 시작"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    logger.info("[COUPON] Starting coupon creation")
    print("[ADMIN] Starting coupon creation")
    
    await query.edit_message_text(
        "🎟️ *쿠폰 발급*\n\n"
        "쿠폰을 받을 사용자의 텔레그램 ID를 입력하세요:\n"
        "(여러 명에게 발급하려면 쉼표로 구분: 123456,789012)\n\n"
        "취소: /cancel",
        parse_mode="Markdown"
    )
    
    return COUPON_USER_ID


async def coupon_user_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """사용자 ID 입력"""
    try:
        user_ids = [int(uid.strip()) for uid in update.message.text.split(',')]
        context.user_data['coupon_user_ids'] = user_ids
        
        await update.message.reply_text(
            f"✅ {len(user_ids)}명의 사용자\n\n"
            "쿠폰 제목을 입력하세요:\n"
            "(예: 신규가입 축하 쿠폰)"
        )
        return COUPON_TITLE
        
    except ValueError:
        await update.message.reply_text("올바른 숫자를 입력하세요.")
        return COUPON_USER_ID


async def coupon_title_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 제목 입력"""
    context.user_data['coupon_title'] = update.message.text.strip()
    
    await update.message.reply_text(
        "쿠폰 설명을 입력하세요:\n"
        "(예: 첫 게임 참여 시 사용 가능)"
    )
    return COUPON_DESC


async def coupon_desc_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 설명 입력"""
    context.user_data['coupon_desc'] = update.message.text.strip()
    
    await update.message.reply_text(
        "할인 금액을 입력하세요 (숫자만):\n"
        "(예: 10000)"
    )
    return COUPON_AMOUNT


async def coupon_amount_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """할인 금액 입력"""
    try:
        amount = int(update.message.text.strip())
        context.user_data['coupon_amount'] = amount
        
        await update.message.reply_text(
            "유효 기간을 입력하세요 (일 수):\n"
            "(예: 30 = 30일 후 만료)\n"
            "무제한이면 0 입력"
        )
        return COUPON_EXPIRES
        
    except ValueError:
        await update.message.reply_text("숫자를 입력하세요.")
        return COUPON_AMOUNT


async def coupon_expires_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """유효기간 입력 및 쿠폰 생성"""
    from datetime import timedelta
    import random
    import string
    
    try:
        days = int(update.message.text.strip())
        expires_at = None if days == 0 else datetime.utcnow() + timedelta(days=days)
        
        db = SessionLocal()
        
        try:
            user_ids = context.user_data['coupon_user_ids']
            title = context.user_data['coupon_title']
            desc = context.user_data['coupon_desc']
            amount = context.user_data['coupon_amount']
            
            created_count = 0
            for user_id in user_ids:
                # 사용자 확인/생성
                user = db.query(User).filter(User.user_id == user_id).first()
                if not user:
                    user = User(user_id=user_id)
                    db.add(user)
                    db.commit()
                
                # 쿠폰 코드 생성
                coupon_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
                
                coupon = Coupon(
                    user_id=user_id,
                    coupon_code=coupon_code,
                    title=title,
                    description=desc,
                    discount_amount=amount,
                    expires_at=expires_at
                )
                db.add(coupon)
                created_count += 1
            
            db.commit()
            
            await update.message.reply_text(
                f"✅ *쿠폰 발급 완료!*\n\n"
                f"📝 제목: {title}\n"
                f"💰 금액: {amount:,}원\n"
                f"👥 발급 인원: {created_count}명\n"
                f"⏰ 유효기간: {'무제한' if days == 0 else f'{days}일'}",
                parse_mode="Markdown"
            )
            
            logger.info(f"Created {created_count} coupons: {title}")
            print(f"[ADMIN] Created {created_count} coupons: {title}")
        except Exception as e:
            logger.error(f"Error creating coupons: {e}", exc_info=True)
            await update.message.reply_text("❌ 쿠폰 발급 중 오류가 발생했습니다.")
            db.rollback()
        finally:
            db.close()
        
    except ValueError:
        await update.message.reply_text("숫자를 입력하세요.")
        return COUPON_EXPIRES
    
    # 사용자 데이터 정리
    context.user_data.pop('coupon_user_ids', None)
    context.user_data.pop('coupon_title', None)
    context.user_data.pop('coupon_desc', None)
    context.user_data.pop('coupon_amount', None)
    
    return ConversationHandler.END


async def coupon_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 발급 취소"""
    context.user_data.pop('coupon_user_ids', None)
    context.user_data.pop('coupon_title', None)
    context.user_data.pop('coupon_desc', None)
    context.user_data.pop('coupon_amount', None)
    await update.message.reply_text("쿠폰 발급이 취소되었습니다.")
    return ConversationHandler.END


def build_coupon_conversation() -> ConversationHandler:
    """쿠폰 발급용 ConversationHandler 인스턴스 생성."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_create_coupon_start, pattern="^admin_create_coupon$")
        ],
        states={
            COUPON_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_user_id_input)],
            COUPON_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_title_input)],
            COUPON_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_desc_input)],
            COUPON_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_amount_input)],
            COUPON_EXPIRES: [MessageHandler(filters.TEXT & ~filters.COMMAND, coupon_expires_input)],
        },
        fallbacks=[
            CommandHandler("cancel", coupon_cancel),
            MessageHandler(filters.COMMAND, coupon_cancel),
        ],
    )


# ==============================
# 이벤트 관리 기능
# ==============================


async def admin_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이벤트 관리 메뉴"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = [
        [InlineKeyboardButton("➕ 이벤트 작성", callback_data="admin_create_event")],
        [InlineKeyboardButton("📋 이벤트 목록", callback_data="admin_list_events")],
        [InlineKeyboardButton("« 뒤로", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(
        "🎉 *이벤트 관리*\n\n"
        "원하는 작업을 선택하세요:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def admin_create_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """이벤트 작성 시작"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    logger.info("[EVENT] Starting event creation")
    print("[ADMIN] Starting event creation")
    
    await query.edit_message_text(
        "🎉 *이벤트 작성*\n\n"
        "이벤트 제목을 입력하세요:\n\n"
        "취소: /cancel",
        parse_mode="Markdown"
    )
    
    return EVENT_TITLE


async def event_title_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """이벤트 제목 입력"""
    context.user_data['event_title'] = update.message.text.strip()
    
    await update.message.reply_text(
        "이벤트 내용을 입력하세요:\n"
        "(여러 줄 가능)"
    )
    return EVENT_CONTENT


async def event_content_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """이벤트 내용 입력"""
    context.user_data['event_content'] = update.message.text.strip()
    
    await update.message.reply_text(
        "이미지 URL을 입력하세요:\n"
        "(JPG, PNG, GIF 모두 가능)\n\n"
        "이미지가 없으면 'skip' 입력"
    )
    return EVENT_IMAGE


async def event_image_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """이미지 URL 입력 및 이벤트 생성"""
    image_url = update.message.text.strip()
    if image_url.lower() == 'skip':
        image_url = None
    
    db = SessionLocal()
    
    try:
        event = Event(
            title=context.user_data['event_title'],
            content=context.user_data['event_content'],
            image_url=image_url
        )
        db.add(event)
        db.commit()
        
        event_id = event.id
        
        await update.message.reply_text(
            f"✅ *이벤트 등록 완료!*\n\n"
            f"📝 제목: {context.user_data['event_title']}\n"
            f"🆔 ID: {event_id}",
            parse_mode="Markdown"
        )
        
        logger.info(f"Created event: {event_id}")
        print(f"[ADMIN] Event created: id={event_id}")
    except Exception as e:
        logger.error(f"Error creating event: {e}", exc_info=True)
        await update.message.reply_text("❌ 이벤트 등록 중 오류가 발생했습니다.")
        db.rollback()
    finally:
        db.close()
    
    # 사용자 데이터 정리
    context.user_data.pop('event_title', None)
    context.user_data.pop('event_content', None)
    
    return ConversationHandler.END


async def event_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """이벤트 작성 취소"""
    context.user_data.pop('event_title', None)
    context.user_data.pop('event_content', None)
    await update.message.reply_text("이벤트 작성이 취소되었습니다.")
    return ConversationHandler.END


def build_event_conversation() -> ConversationHandler:
    """이벤트 작성용 ConversationHandler 인스턴스 생성."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_create_event_start, pattern="^admin_create_event$")
        ],
        states={
            EVENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_title_input)],
            EVENT_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_content_input)],
            EVENT_IMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, event_image_input)],
        },
        fallbacks=[
            CommandHandler("cancel", event_cancel),
            MessageHandler(filters.COMMAND, event_cancel),
        ],
    )

