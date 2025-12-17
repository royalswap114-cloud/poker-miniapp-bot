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

# Conversation 상태 정의 (방 생성 플로우 - 6단계)
(
    ROOM_NAME,
    ROOM_URL,
    ROOM_BLINDS,
    ROOM_BUYIN,
    ROOM_TIME,
    ROOM_CONTACT,
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

# 쿠폰 사용 처리 플로우 상태
USE_COUPON_CODE = 250

# 이벤트 관리 플로우 상태
(
    EVENT_TITLE,
    EVENT_CONTENT,
    EVENT_IMAGE,
) = range(210, 213)

# 방 수정 플로우 상태
(
    EDIT_ROOM_SELECT,
    EDIT_ROOM_FIELD,
    EDIT_ROOM_VALUE,
) = range(300, 303)


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
        "🏠 <b>새 방 만들기 (1/6)</b>\n\n"
        "📝 방 이름을 입력하세요:\n"
        "(예: 에르메스홀덤 1번방)\n\n"
        "취소: /cancel"
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
        f"✅ 방 이름: {room_name}\n\n"
        "🏠 <b>새 방 만들기 (2/6)</b>\n\n"
        "🔗 방 URL을 입력하세요:\n"
        "(예: https://www.pokernow.club/games/xxxxx)"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    return ROOM_URL


async def admin_create_room_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: 방 URL 입력."""
    room_url = update.message.text.strip()
    if not room_url.startswith("http"):
        await update.message.reply_text(
            "❌ 올바른 URL을 입력하세요.\n"
            "(http:// 또는 https://로 시작해야 합니다)"
        )
        return ROOM_URL

    context.user_data["room_data"]["room_url"] = room_url

    text = (
        f"✅ 방 URL: {room_url}\n\n"
        "🏠 <b>새 방 만들기 (3/6)</b>\n\n"
        "💰 블라인드를 입력하세요:\n"
        "(예: 1만/2만)"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    return ROOM_BLINDS


async def admin_create_room_blinds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: 블라인드 입력."""
    blinds = update.message.text.strip()
    if not blinds:
        await update.message.reply_text("블라인드를 입력해 주세요.")
        return ROOM_BLINDS

    context.user_data["room_data"]["blinds"] = blinds

    text = (
        f"✅ 블라인드: {blinds}\n\n"
        "🏠 <b>새 방 만들기 (4/6)</b>\n\n"
        "💵 최소 바이인을 입력하세요:\n"
        "(예: 100만~500만)"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    return ROOM_BUYIN


async def admin_create_room_buyin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 4: 최소 바이인 입력."""
    min_buyin = update.message.text.strip()
    if not min_buyin:
        await update.message.reply_text("최소 바이인을 입력해 주세요.")
        return ROOM_BUYIN

    context.user_data["room_data"]["min_buyin"] = min_buyin

    text = (
        f"✅ 최소 바이인: {min_buyin}\n\n"
        "🏠 <b>새 방 만들기 (5/6)</b>\n\n"
        "⏰ 게임 시간을 입력하세요:\n"
        "(예: 24시간 매너타임 1시간)"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    return ROOM_TIME


async def admin_create_room_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 5: 게임 시간 입력."""
    game_time = update.message.text.strip()
    if not game_time:
        await update.message.reply_text("게임 시간을 입력해 주세요.")
        return ROOM_TIME

    context.user_data["room_data"]["game_time"] = game_time

    text = (
        f"✅ 게임 시간: {game_time}\n\n"
        "🏠 <b>새 방 만들기 (6/6)</b>\n\n"
        "📱 바인/아웃 담당자 텔레그램 ID를 입력하세요:\n"
        "(예: ROYAL_USDT_TRX)\n\n"
        "⚠️ @ 기호는 빼고 입력하세요\n"
        "스킵하려면 'skip' 입력"
    )
    await update.message.reply_text(text, parse_mode="HTML")

    return ROOM_CONTACT




async def admin_create_room_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 6: 연락처 입력 및 DB 저장."""
    contact_input = update.message.text.strip()
    
    # @ 기호 제거 및 스킵 처리
    if contact_input.lower() in ["skip", "스킵", "없음", "-"]:
        contact_telegram = None
    else:
        contact_telegram = contact_input.replace('@', '').strip()

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
            contact_telegram=contact_telegram,
            current_players=0,
            max_players=10,
            status="active"
        )
        db.add(room)
        db.commit()
        db.refresh(room)

        # 성공 메시지
        contact_text = f"📱 담당자: @{room.contact_telegram}" if room.contact_telegram else "📱 담당자: 미설정"
        
        success_text = (
            "✅ <b>방 생성 완료!</b>\n\n"
            f"📝 이름: {room.room_name}\n"
            f"🔗 URL: {room.room_url}\n"
            f"💰 블라인드: {room.blinds}\n"
            f"💵 최소 바이인: {room.min_buyin}\n"
            f"⏰ 게임 시간: {room.game_time}\n"
            f"{contact_text}\n"
            f"👥 최대 인원: 10명"
        )

        await update.message.reply_text(success_text, parse_mode="HTML")

        logger.info(
            "방 생성 완료: room_id=%s, room_name=%s, contact=%s, user_id=%s",
            room.id,
            room.room_name,
            contact_telegram,
            update.effective_user.id,
        )
        print(f"[ADMIN] Room created: id={room.id}, name={room.room_name}, contact={contact_telegram}")

    except Exception as e:
        logger.error("방 생성 중 오류 발생: %s", e, exc_info=True)
        print(f"[ERROR] Failed to create room: {e}")
        await update.message.reply_text(
            f"❌ <b>방 생성 실패</b>\n\n"
            f"오류: {str(e)}",
            parse_mode="HTML"
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
        "🎨 <b>새 배너 만들기</b>\n\n"
        "📸 <b>권장 사이즈:</b>\n"
        "• 1200 x 400px (3:1 비율)\n"
        "• 파일 크기: 500KB 이하\n"
        "• GIF: 2MB 이하\n\n"
        "배너 이미지 URL을 입력하세요:\n"
        "(JPG, PNG, GIF 지원)\n\n"
        "취소: /cancel"
    )
    if query:
        await query.message.reply_text(text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

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
        # ConversationHandler가 처리 (build_edit_room_conversation)
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

    if data == "admin_list_coupons":
        # 별도 콜백 핸들러에서 처리 (poker_miniapp_bot.py)
        return

    if data == "admin_use_coupon":
        # ConversationHandler가 처리
        return

    # ===== 이벤트 관리 =====
    if data == "admin_events":
        await admin_events(update, context)
        return

    if data == "admin_create_event":
        # ConversationHandler가 처리
        return

    if data == "admin_list_events":
        # 별도 콜백 핸들러에서 처리 (poker_miniapp_bot.py)
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
            ROOM_BLINDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_blinds)
            ],
            ROOM_BUYIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_buyin)
            ],
            ROOM_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_time)
            ],
            ROOM_CONTACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_create_room_contact)
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
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            await query.edit_message_text(
                "등록된 방이 없습니다.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« 뒤로", callback_data="admin_menu")]
                ])
            )
            return
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = []
        for room in rooms:
            status_emoji = "🟢" if room.status == "active" else "🔴"
            keyboard.append([InlineKeyboardButton(
                f"{status_emoji} {room.room_name} ({room.current_players}/{room.max_players})",
                callback_data=f"edit_room_select_{room.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("« 뒤로", callback_data="admin_menu")])
        
        await query.edit_message_text(
            "✏️ <b>방 수정</b>\n\n"
            "수정할 방을 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    finally:
        db.close()


async def admin_edit_room_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """수정할 방 선택 후 필드 선택"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    room_id = int(query.data.split("_")[-1])
    context.user_data['edit_room_id'] = room_id
    
    db = SessionLocal()
    
    try:
        room = db.query(Room).filter(Room.id == room_id).first()
        
        if not room:
            await query.edit_message_text("방을 찾을 수 없습니다.")
            return ConversationHandler.END
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        # HTML 이스케이프
        from html import escape
        name = escape(room.room_name)
        url = escape(room.room_url)
        blinds = escape(room.blinds or '-')
        buyin = escape(room.min_buyin or '-')
        game_time = escape(room.game_time or '-')
        contact = escape(room.contact_telegram or '-')
        
        keyboard = [
            [InlineKeyboardButton("📝 방 이름", callback_data="edit_field_name")],
            [InlineKeyboardButton("🔗 방 URL", callback_data="edit_field_url")],
            [InlineKeyboardButton("💰 블라인드", callback_data="edit_field_blinds")],
            [InlineKeyboardButton("💵 최소 바이인", callback_data="edit_field_min_buyin")],
            [InlineKeyboardButton("⏰ 게임 시간", callback_data="edit_field_game_time")],
            [InlineKeyboardButton("📱 담당자 ID", callback_data="edit_field_contact")],
            [InlineKeyboardButton("👥 최대 인원", callback_data="edit_field_max_players")],
            [InlineKeyboardButton("👤 현재 인원", callback_data="edit_field_current_players")],
            [InlineKeyboardButton("🔄 상태", callback_data="edit_field_status")],
            [InlineKeyboardButton("« 취소", callback_data="admin_update_room")]
        ]
        
        await query.edit_message_text(
            f"✏️ <b>방 수정: {name}</b>\n\n"
            f"<b>방 이름:</b> {name}\n"
            f"<b>방 URL:</b> {url}\n"
            f"<b>블라인드:</b> {blinds}\n"
            f"<b>최소 바이인:</b> {buyin}\n"
            f"<b>게임 시간:</b> {game_time}\n"
            f"<b>담당자:</b> {contact}\n"
            f"<b>최대 인원:</b> {room.max_players}\n"
            f"<b>현재 인원:</b> {room.current_players}\n"
            f"<b>상태:</b> {room.status}\n\n"
            "수정할 항목을 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        
        return EDIT_ROOM_FIELD
        
    finally:
        db.close()


async def admin_edit_room_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """수정할 필드 선택"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    field = query.data.split("_")[-1]
    context.user_data['edit_field'] = field
    
    field_names = {
        'name': '방 이름',
        'url': '방 URL',
        'blinds': '블라인드',
        'min_buyin': '최소 바이인',
        'game_time': '게임 시간',
        'contact': '담당자 텔레그램 ID',
        'max_players': '최대 인원',
        'current_players': '현재 인원',
        'status': '상태'
    }
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    if field == 'status':
        # 상태는 직접 선택
        keyboard = [
            [InlineKeyboardButton("🟢 활성", callback_data="edit_status_active")],
            [InlineKeyboardButton("🔴 비활성", callback_data="edit_status_inactive")],
            [InlineKeyboardButton("« 취소", callback_data="admin_update_room")]
        ]
        
        await query.edit_message_text(
            "🔄 <b>상태 변경</b>\n\n"
            "변경할 상태를 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return EDIT_ROOM_FIELD
    else:
        from html import escape
        field_name_escaped = escape(field_names[field])
        await query.edit_message_text(
            f"✏️ <b>{field_name_escaped} 수정</b>\n\n"
            f"새로운 {field_name_escaped}을(를) 입력하세요:\n\n"
            "취소: /cancel",
            parse_mode="HTML"
        )
        return EDIT_ROOM_VALUE


async def admin_edit_room_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """상태 변경 처리"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    new_status = query.data.split("_")[-1]
    room_id = context.user_data.get('edit_room_id')
    
    if not room_id:
        await query.edit_message_text("오류가 발생했습니다. 다시 시도해주세요.")
        return ConversationHandler.END
    
    db = SessionLocal()
    
    try:
        room = db.query(Room).filter(Room.id == room_id).first()
        
        if room:
            room.status = new_status
            db.commit()
            
            status_text = "활성" if new_status == "active" else "비활성"
            
            from html import escape
            room_name_escaped = escape(room.room_name)
            await query.edit_message_text(
                f"✅ <b>상태 변경 완료!</b>\n\n"
                f"방 이름: {room_name_escaped}\n"
                f"상태: {status_text}",
                parse_mode="HTML"
            )
            
            logger.info(f"[ADMIN] 방 상태 변경: {room_id} → {new_status}")
        else:
            await query.edit_message_text("방을 찾을 수 없습니다.")
        
    finally:
        db.close()
    
    return ConversationHandler.END


async def admin_edit_room_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """새 값 입력 및 업데이트"""
    room_id = context.user_data.get('edit_room_id')
    field = context.user_data.get('edit_field')
    new_value = update.message.text.strip()
    
    if not room_id or not field:
        await update.message.reply_text("오류가 발생했습니다. 다시 시도해주세요.")
        return ConversationHandler.END
    
    db = SessionLocal()
    
    try:
        room = db.query(Room).filter(Room.id == room_id).first()
        
        if not room:
            await update.message.reply_text("방을 찾을 수 없습니다.")
            return ConversationHandler.END
        
        # 필드별 검증 및 업데이트
        if field == 'name':
            room.room_name = new_value
        elif field == 'url':
            if not new_value.startswith('http'):
                await update.message.reply_text("올바른 URL을 입력하세요 (http:// 또는 https://)")
                return EDIT_ROOM_VALUE
            room.room_url = new_value
        elif field == 'blinds':
            room.blinds = new_value
        elif field == 'min_buyin':
            room.min_buyin = new_value
        elif field == 'game_time':
            room.game_time = new_value
        elif field == 'contact':
            # @ 기호 제거 및 스킵 처리
            if new_value.lower() in ["skip", "스킵", "없음", "-"]:
                room.contact_telegram = None
            else:
                room.contact_telegram = new_value.replace('@', '').strip()
        elif field == 'max_players':
            try:
                max_players = int(new_value)
                if max_players < 1 or max_players > 100:
                    await update.message.reply_text("1~100 사이의 숫자를 입력하세요.")
                    return EDIT_ROOM_VALUE
                room.max_players = max_players
            except ValueError:
                await update.message.reply_text("숫자를 입력하세요.")
                return EDIT_ROOM_VALUE
        elif field == 'current_players':
            try:
                current_players = int(new_value)
                if current_players < 0 or current_players > room.max_players:
                    await update.message.reply_text(f"0~{room.max_players} 사이의 숫자를 입력하세요.")
                    return EDIT_ROOM_VALUE
                room.current_players = current_players
            except ValueError:
                await update.message.reply_text("숫자를 입력하세요.")
                return EDIT_ROOM_VALUE
        
        db.commit()
        
        field_names = {
            'name': '방 이름',
            'url': '방 URL',
            'blinds': '블라인드',
            'min_buyin': '최소 바이인',
            'game_time': '게임 시간',
            'contact': '담당자 ID',
            'max_players': '최대 인원',
            'current_players': '현재 인원'
        }
        
        from html import escape
        field_name_escaped = escape(field_names[field])
        room_name_escaped = escape(room.room_name)
        new_value_escaped = escape(new_value)
        
        await update.message.reply_text(
            f"✅ <b>{field_name_escaped} 수정 완료!</b>\n\n"
            f"방 이름: {room_name_escaped}\n"
            f"새로운 값: {new_value_escaped}",
            parse_mode="HTML"
        )
        
        logger.info(f"[ADMIN] 방 수정: {room_id}, {field} → {new_value}")
        
    finally:
        db.close()
    
    return ConversationHandler.END


async def edit_room_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """방 수정 취소"""
    context.user_data.pop('edit_room_id', None)
    context.user_data.pop('edit_field', None)
    await update.message.reply_text("방 수정이 취소되었습니다.")
    return ConversationHandler.END


def build_edit_room_conversation() -> ConversationHandler:
    """방 수정용 ConversationHandler 인스턴스 생성."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_edit_room_list, pattern="^admin_update_room$"),
            CallbackQueryHandler(admin_edit_room_select, pattern="^edit_room_select_")
        ],
        states={
            EDIT_ROOM_FIELD: [
                CallbackQueryHandler(admin_edit_room_field, pattern="^edit_field_"),
                CallbackQueryHandler(admin_edit_room_status, pattern="^edit_status_")
            ],
            EDIT_ROOM_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_room_value)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", edit_room_cancel),
            MessageHandler(filters.COMMAND, edit_room_cancel),
            CallbackQueryHandler(admin_edit_room_list, pattern="^admin_update_room$")
        ],
    )


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
        [InlineKeyboardButton("✅ 쿠폰 사용 처리", callback_data="admin_use_coupon")],
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


async def admin_use_coupon_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 사용 처리 시작"""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    
    await query.answer()
    
    await query.edit_message_text(
        "✅ *쿠폰 사용 처리*\n\n"
        "사용할 쿠폰 코드를 입력하세요:\n"
        "(예: DIE93K2Y83)\n\n"
        "취소: /cancel",
        parse_mode="Markdown"
    )
    
    return USE_COUPON_CODE


async def use_coupon_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 코드 입력 및 사용 처리"""
    coupon_code = update.message.text.strip().upper()
    
    db = SessionLocal()
    
    try:
        # 쿠폰 조회
        coupon = db.query(Coupon).filter(Coupon.coupon_code == coupon_code).first()
        
        if not coupon:
            await update.message.reply_text(
                f"❌ *쿠폰을 찾을 수 없습니다*\n\n"
                f"입력한 코드: `{coupon_code}`\n\n"
                "올바른 쿠폰 코드를 확인해주세요.",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        # 이미 사용된 쿠폰인지 확인
        if coupon.is_used:
            used_date = coupon.used_at.strftime('%Y-%m-%d %H:%M') if coupon.used_at else '알 수 없음'
            
            await update.message.reply_text(
                f"⚠️ *이미 사용된 쿠폰입니다*\n\n"
                f"📝 제목: {coupon.title}\n"
                f"💰 금액: {coupon.discount_amount:,}원\n"
                f"👤 사용자 ID: {coupon.user_id}\n"
                f"📅 사용 일시: {used_date}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        # 쿠폰 만료 확인
        if coupon.expires_at and coupon.expires_at < datetime.utcnow():
            expire_date = coupon.expires_at.strftime('%Y-%m-%d')
            
            await update.message.reply_text(
                f"⏰ *만료된 쿠폰입니다*\n\n"
                f"📝 제목: {coupon.title}\n"
                f"💰 금액: {coupon.discount_amount:,}원\n"
                f"📅 만료일: {expire_date}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END
        
        # 쿠폰 사용 처리
        coupon.is_used = True
        coupon.used_at = datetime.utcnow()
        db.commit()
        
        await update.message.reply_text(
            f"✅ *쿠폰 사용 처리 완료!*\n\n"
            f"📝 제목: {coupon.title}\n"
            f"💰 금액: {coupon.discount_amount:,}원\n"
            f"👤 사용자 ID: {coupon.user_id}\n"
            f"🎟️ 쿠폰 코드: `{coupon_code}`",
            parse_mode="Markdown"
        )
        
        logger.info(f"[ADMIN] 쿠폰 사용 처리: {coupon_code} (user_id: {coupon.user_id})")
        
    finally:
        db.close()
    
    return ConversationHandler.END


async def use_coupon_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """쿠폰 사용 처리 취소"""
    await update.message.reply_text("쿠폰 사용 처리가 취소되었습니다.")
    return ConversationHandler.END


def build_use_coupon_conversation() -> ConversationHandler:
    """쿠폰 사용 처리용 ConversationHandler 인스턴스 생성."""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_use_coupon_start, pattern="^admin_use_coupon$")
        ],
        states={
            USE_COUPON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, use_coupon_code_input)]
        },
        fallbacks=[
            CommandHandler("cancel", use_coupon_cancel),
            MessageHandler(filters.COMMAND, use_coupon_cancel),
        ],
    )


async def admin_list_coupons_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """쿠폰 목록 조회"""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    db = SessionLocal()
    
    try:
        # 최근 10개 쿠폰 조회
        coupons = db.query(Coupon).order_by(Coupon.created_at.desc()).limit(10).all()
        
        if not coupons:
            await query.edit_message_text("등록된 쿠폰이 없습니다.")
            return
        
        message = "📋 *최근 쿠폰 목록*\n\n"
        
        for coupon in coupons:
            status = "✅ 사용" if coupon.is_used else "⏳ 미사용"
            message += f"{status} `{coupon.coupon_code}`\n"
            message += f"  └ {coupon.title} ({coupon.discount_amount:,}원)\n"
            message += f"  └ User: {coupon.user_id}\n\n"
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = [[InlineKeyboardButton("« 뒤로", callback_data="admin_coupons")]]
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    finally:
        db.close()


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
        "🎉 <b>이벤트 관리</b>\n\n"
        "원하는 작업을 선택하세요:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def admin_list_events(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이벤트 목록 조회"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    logger.info("[ADMIN] 이벤트 목록 버튼 클릭됨")
    print(f"[ADMIN] 이벤트 목록 버튼 클릭: user_id={query.from_user.id if query.from_user else None}")
    
    db = SessionLocal()
    
    try:
        events = db.query(Event).order_by(Event.created_at.desc()).all()
        
        logger.info(f"[ADMIN] 이벤트 {len(events)}개 조회됨")
        print(f"[ADMIN] 이벤트 {len(events)}개 조회됨")
        
        if not events:
            await query.edit_message_text(
                "등록된 이벤트가 없습니다.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« 뒤로", callback_data="admin_events")]
                ])
            )
            return
        
        keyboard = []
        for event in events:
            status_emoji = "✅" if event.status == "active" else "❌"
            # 제목 길이 제한 (텔레그램 버튼 길이 제한)
            title = event.title[:25] + "..." if len(event.title) > 25 else event.title
            keyboard.append([InlineKeyboardButton(
                f"{status_emoji} {title}",
                callback_data=f"event_detail_{event.id}"
            )])
        
        keyboard.append([InlineKeyboardButton("« 뒤로", callback_data="admin_events")])
        
        await query.edit_message_text(
            "📋 이벤트 목록\n\n이벤트를 선택하세요:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"[ERROR] 이벤트 목록 오류: {e}", exc_info=True)
        print(f"[ERROR] 이벤트 목록 오류: {e}")
        try:
            await query.edit_message_text(f"오류 발생: {str(e)}")
        except:
            await query.message.reply_text(f"오류 발생: {str(e)}")
    finally:
        db.close()


async def admin_event_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이벤트 상세 보기"""
    from bot.database import SessionLocal, Event
    from html import escape
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    try:
        event_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("잘못된 이벤트 ID입니다.")
        return
    
    db = SessionLocal()
    
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if not event:
            await query.edit_message_text(
                "이벤트를 찾을 수 없습니다.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« 목록", callback_data="admin_list_events")]
                ])
            )
            return
        
        title = escape(event.title)
        content = escape(event.content)[:200]
        
        keyboard = [
            [InlineKeyboardButton("🗑 삭제", callback_data=f"event_delete_confirm_{event_id}")],
            [InlineKeyboardButton("🔄 상태 변경", callback_data=f"event_toggle_{event_id}")],
            [InlineKeyboardButton("« 목록", callback_data="admin_list_events")]
        ]
        
        status_text = "활성" if event.status == "active" else "비활성"
        
        await query.edit_message_text(
            f"📋 이벤트 상세\n\n"
            f"제목: {title}\n\n"
            f"내용: {content}...\n\n"
            f"상태: {status_text}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logger.error(f"[ERROR] 이벤트 상세 오류: {e}", exc_info=True)
        print(f"[ERROR] 이벤트 상세 오류: {e}")
        try:
            await query.edit_message_text(f"오류 발생: {str(e)}")
        except:
            await query.message.reply_text(f"오류 발생: {str(e)}")
    finally:
        db.close()


async def admin_event_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이벤트 삭제 확인"""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    try:
        event_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("잘못된 이벤트 ID입니다.")
        return
    
    keyboard = [
        [InlineKeyboardButton("✅ 삭제 확인", callback_data=f"event_delete_exec_{event_id}")],
        [InlineKeyboardButton("❌ 취소", callback_data=f"event_detail_{event_id}")]
    ]
    
    await query.edit_message_text(
        "⚠️ 이벤트 삭제\n\n정말 삭제하시겠습니까?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def admin_event_delete_exec(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이벤트 삭제 실행"""
    from bot.database import SessionLocal, Event
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    try:
        event_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("잘못된 이벤트 ID입니다.")
        return
    
    db = SessionLocal()
    
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if event:
            title = event.title
            db.delete(event)
            db.commit()
            
            await query.edit_message_text(
                f"✅ 이벤트 삭제 완료\n\n제목: {title}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« 목록", callback_data="admin_list_events")]
                ])
            )
            
            logger.info(f"[ADMIN] 이벤트 삭제: {event_id}")
            print(f"[ADMIN] 이벤트 삭제: {event_id}")
        else:
            await query.edit_message_text("이벤트를 찾을 수 없습니다.")
        
    except Exception as e:
        logger.error(f"[ERROR] 이벤트 삭제 오류: {e}", exc_info=True)
        print(f"[ERROR] 이벤트 삭제 오류: {e}")
        db.rollback()
        try:
            await query.edit_message_text(f"오류 발생: {str(e)}")
        except:
            await query.message.reply_text(f"오류 발생: {str(e)}")
    finally:
        db.close()


async def admin_event_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """이벤트 상태 변경"""
    from bot.database import SessionLocal, Event
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    try:
        event_id = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("잘못된 이벤트 ID입니다.")
        return
    
    db = SessionLocal()
    
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if event:
            event.status = "inactive" if event.status == "active" else "active"
            db.commit()
            
            status_text = "활성" if event.status == "active" else "비활성"
            
            await query.edit_message_text(
                f"✅ 상태 변경 완료\n\n"
                f"제목: {event.title}\n"
                f"새 상태: {status_text}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("« 상세", callback_data=f"event_detail_{event_id}")],
                    [InlineKeyboardButton("« 목록", callback_data="admin_list_events")]
                ])
            )
            
            logger.info(f"[ADMIN] 이벤트 상태 변경: {event_id} → {event.status}")
            print(f"[ADMIN] 이벤트 상태 변경: {event_id} → {event.status}")
        else:
            await query.edit_message_text("이벤트를 찾을 수 없습니다.")
        
    except Exception as e:
        logger.error(f"[ERROR] 이벤트 상태 변경 오류: {e}", exc_info=True)
        print(f"[ERROR] 이벤트 상태 변경 오류: {e}")
        db.rollback()
        try:
            await query.edit_message_text(f"오류 발생: {str(e)}")
        except:
            await query.message.reply_text(f"오류 발생: {str(e)}")
    finally:
        db.close()


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

