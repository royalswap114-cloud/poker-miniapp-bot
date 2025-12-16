"""
poker_miniapp_bot.py

단일 파일 텔레그램 봇:
- /start, /help, /stats, /admin 명령어 제공
- PokerNow 미니앱(WebApp) 버튼 제공
- 관리자 권한 체크 (/admin)
- .env 를 통한 BOT_TOKEN, ADMIN_IDS 로딩
- 로깅 + print 로 디버깅 가능

python-telegram-bot v21.x 기준 (ApplicationBuilder 사용)
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Set

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ==============================
# 환경 변수 / 기본 설정
# ==============================

# .env 파일 로드
load_dotenv()


def _parse_admin_ids(value: str | None) -> Set[int]:
    """
    쉼표(,)로 구분된 ADMIN_IDS 문자열을 정수 set 으로 변환.
    예: "123,456" -> {123, 456}
    """
    if not value:
        return set()
    ids: Set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            print(f"[WARN] ADMIN_IDS 에 잘못된 값이 포함되어 있습니다: {part}")
    return ids


# 환경변수에서 토큰/관리자 ID / 미니앱 URL 읽기
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8000")


# ==============================
# 로깅 설정
# ==============================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,  # 필요 시 DEBUG 로 변경
)
logger = logging.getLogger(__name__)

# is_admin 함수는 이제 bot.utils 에서 import 합니다.
from bot.utils import is_admin


# ==============================
# 간단한 인-메모리 통계 저장소
# (실 서비스면 DB/파일로 대체 권장)
# ==============================

# 예: {user_id: {"username": "...", "play_count": 3}}
user_stats: Dict[int, Dict[str, int | str]] = {}


def increase_play_count(user_id: int, username: str | None) -> None:
    """사용자 플레이 횟수 +1"""
    if user_id not in user_stats:
        user_stats[user_id] = {
            "username": username or "",
            "play_count": 0,
        }
    user_stats[user_id]["play_count"] = int(user_stats[user_id]["play_count"]) + 1


# ==============================
# 토큰 / 설정 디버그 유틸
# ==============================

def debug_token_startup_check() -> None:
    """봇 시작 시 토큰/관리자 설정을 콘솔에 출력해서 확인."""
    print("===== BOT 설정 확인 =====")
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN 이 설정되지 않았습니다. .env 를 확인하세요.")
        logger.error("BOT_TOKEN 이 설정되지 않았습니다. .env 또는 환경변수를 확인하세요.")
    else:
        print(f"[INFO] BOT_TOKEN 길이: {len(BOT_TOKEN)}")
        print(f"[INFO] BOT_TOKEN 앞 10글자: {BOT_TOKEN[:10]}***")
        logger.info("BOT_TOKEN 이 설정되었습니다. 길이=%s", len(BOT_TOKEN))

    print(f"[INFO] ADMIN_IDS 로드됨: {sorted(list(ADMIN_IDS))}")
    logger.info("ADMIN_IDS: %s", ADMIN_IDS)
    print(f"[INFO] 미니앱 URL: {WEBAPP_URL}")
    logger.info("WEBAPP_URL: %s", WEBAPP_URL)
    print("==========================")


async def debug_token_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /debug_token - 토큰/관리자 설정 상태를 유저에게 간단히 보여줌.
    실제 토큰 전체는 절대 노출하지 않음.
    """
    user = update.effective_user
    logger.info("명령어 실행: /debug_token, 사용자: %s", user.id if user else None)
    print(f"[CMD] /debug_token from {user.id if user else None}")

    if not BOT_TOKEN:
        await update.message.reply_text("❌ BOT_TOKEN 이 설정되지 않았습니다.")
        return

    text = (
        "✅ BOT_TOKEN 이 설정되어 있습니다.\n"
        f"- 길이: {len(BOT_TOKEN)}\n"
        f"- 앞 10글자: {BOT_TOKEN[:10]}***\n"
        f"- ADMIN_IDS: {sorted(list(ADMIN_IDS))}\n"
        "\n(실제 토큰 전체는 보안상 절대 표시하지 않습니다.)"
    )
    await update.message.reply_text(text)


# ==============================
# 핸들러들
# ==============================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """사용자가 /start 를 입력했을 때 호출되는 함수"""
    user = update.effective_user
    logger.info("명령어 실행: /start, 사용자: %s", user.id if user else None)
    print(f"[CMD] /start from {user.id if user else None}")

    # 사용자 정보를 DB에 저장/업데이트
    from bot.database import SessionLocal, User
    from datetime import datetime
    
    db = SessionLocal()
    try:
        db_user = db.query(User).filter(User.user_id == user.id).first()
        if not db_user:
            db_user = User(
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                created_at=datetime.utcnow()
            )
            db.add(db_user)
            logger.info(f"새 사용자 등록: {user.id} (@{user.username})")
            print(f"[DB] 새 사용자 등록: {user.id} (@{user.username})")
        else:
            # 기존 사용자 정보 업데이트
            db_user.username = user.username
            db_user.first_name = user.first_name
            logger.info(f"사용자 정보 업데이트: {user.id}")
            print(f"[DB] 사용자 정보 업데이트: {user.id}")
        
        db.commit()
    except Exception as e:
        logger.error(f"사용자 정보 저장 실패: {e}", exc_info=True)
        print(f"[ERROR] 사용자 정보 저장 실패: {e}")
        db.rollback()
    finally:
        db.close()

    # WebApp URL 검증 및 로깅
    print(f"[WEBAPP] URL: {WEBAPP_URL}")
    logger.info(f"WebApp URL: {WEBAPP_URL}")
    
    if not WEBAPP_URL.startswith(('http://', 'https://')):
        logger.warning(f"WebApp URL이 올바른 형식이 아닙니다: {WEBAPP_URL}")
        print(f"[WARN] WebApp URL이 올바른 형식이 아닙니다: {WEBAPP_URL}")

    # URL에 사용자 정보 포함 (URL 인코딩)
    from urllib.parse import urlencode
    
    user_params = {
        'user_id': user.id,
        'first_name': user.first_name or '',
        'last_name': user.last_name or '',
        'username': user.username or ''
    }
    
    webapp_url_with_params = f"{WEBAPP_URL}?{urlencode(user_params)}"
    logger.info(f"WebApp URL with params: {webapp_url_with_params}")
    print(f"[WEBAPP] URL with params: {webapp_url_with_params}")

    # WebApp 버튼 (커스텀 미니앱 UI 열기 - 사용자 정보 포함된 URL)
    webapp_button = InlineKeyboardButton(
        text="🃏 홀덤테이블",
        web_app=WebAppInfo(url=webapp_url_with_params),  # 텔레그램 내 WebView 로 커스텀 미니앱 열기
    )

    # 제휴업체목록 버튼 (callback query)
    partners_button = InlineKeyboardButton(
        text="🤝 제휴업체목록",
        callback_data="partners_list",
    )

    keyboard = InlineKeyboardMarkup(
        [
            [webapp_button],
            [partners_button],
        ]
    )

    welcome_text = (
        "텔레그램 NO.1 홀덤 로얄커뮤니티 입니다.\n\n"
        "검증된 업체에서 언제든지 실시간으로 테이블을 확인하여,\n"
        "언제든지 게임에 참여해보세요\n\n"
        "🃏 <b>홀덤테이블</b> - 실시간 홀덤방 테이블 목록을 확인하고 게임에 참여하세요.\n"
        "🤝 <b>제휴업체목록</b> - 제휴 업체 정보를 확인하세요."
    )

    await update.message.reply_html(welcome_text, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """도움말 메시지 (/help)."""
    user = update.effective_user
    logger.info("명령어 실행: /help, 사용자: %s", user.id if user else None)
    print(f"[CMD] /help from {user.id if user else None}")

    text = (
        "TTPOKER 봇 사용 방법:\n\n"
        "- /start : 미니앱 열기 버튼 표시\n"
        "- /stats : 내 참여 통계 확인\n"
        "- /admin : 관리자 메뉴 (관리자만)\n"
        "- /debug_token : 토큰/설정 상태 확인\n"
    )
    await update.message.reply_text(text)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    InlineKeyboard 버튼 클릭 처리 (callback_query) - 일반 유저용.
    관리자 콜백은 bot/handlers/admin.py 의 admin_callback_handler 가 처리합니다.
    """
    query = update.callback_query
    await query.answer()  # 로딩 아이콘 제거

    data = query.data
    user = query.from_user
    logger.info("Callback 실행: data=%s, user_id=%s", data, user.id if user else None)
    print(f"[CB] data={data} from {user.id if user else None}")

    # 제휴업체목록 버튼
    if data == "partners_list":
        # 임시로 "준비중" 메시지 표시 (나중에 채널 연동 예정)
        msg = (
            "🤝 제휴업체목록\n\n"
            "현재 준비 중입니다.\n"
            "곧 제휴 업체 정보를 확인할 수 있습니다.\n\n"
            "문의: @royalswap_kr"
        )
        await query.message.reply_text(msg)
        return


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """사용자 개인 통계 확인 (/stats)."""
    user = update.effective_user
    logger.info("명령어 실행: /stats, 사용자: %s", user.id if user else None)
    print(f"[CMD] /stats from {user.id if user else None}")

    info = user_stats.get(user.id)

    if not info:
        await update.message.reply_text(
            "아직 기록된 게임이 없습니다.\n"
            "먼저 '게임 시작하기' 버튼을 눌러보세요."
        )
        return

    username = info.get("username") or user.username or "(이름 없음)"
    play_count = info.get("play_count", 0)

    text = (
        f"👤 사용자: @{username}\n"
        f"🃏 기록된 플레이 횟수: {play_count} 회"
    )
    await update.message.reply_text(text)


# admin_command 함수는 이제 bot/handlers/admin.py 의 admin_menu 로 이동했습니다.


# ==============================
# 에러 핸들러
# ==============================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """모든 예외를 여기서 받아서 로깅 + 간단 안내."""
    logger.error("업데이트 처리 중 예외 발생: %s", context.error, exc_info=True)
    print(f"[ERROR] {context.error}")

    # 가능하면 사용자에게도 알려주기 (조용히 실패하고 싶으면 주석 처리)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ 알 수 없는 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            )
    except Exception:
        # 여기서 또 에러 나면 그냥 무시
        pass


# ==============================
# 메인 엔트리 포인트
# ==============================

def main() -> None:
    """봇 실행 메인 함수"""
    debug_token_startup_check()

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN 이 없습니다. .env 파일을 확인하고 다시 실행하세요.")
        return

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # 명령어 핸들러 등록
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("debug_token", debug_token_command))

    # 관리자 핸들러 등록 (bot/handlers/admin.py)
    from bot.handlers.admin import (
        admin_menu,
        admin_callback_handler,
        build_admin_create_room_conversation,
        build_edit_room_conversation,
        build_banner_create_conversation,
        build_update_players_conversation,
        build_coupon_conversation,
        build_use_coupon_conversation,
        build_event_conversation,
        admin_delete_room_confirm,
        admin_list_coupons_callback,
        admin_list_events,
        admin_event_detail,
        admin_event_delete,
        admin_event_toggle,
    )

    application.add_handler(CommandHandler("admin", admin_menu))
    
    # ConversationHandlers (순서 중요! 먼저 등록)
    application.add_handler(build_admin_create_room_conversation())
    application.add_handler(build_edit_room_conversation())
    application.add_handler(build_banner_create_conversation())
    application.add_handler(build_update_players_conversation())
    application.add_handler(build_coupon_conversation())
    application.add_handler(build_use_coupon_conversation())
    application.add_handler(build_event_conversation())
    
    # 관리자 콜백 핸들러 (admin_ 패턴)
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    
    # 쿠폰 목록 조회 콜백 핸들러
    application.add_handler(CallbackQueryHandler(admin_list_coupons_callback, pattern="^admin_list_coupons$"))
    
    # 이벤트 관련 콜백 핸들러
    application.add_handler(CallbackQueryHandler(admin_list_events, pattern="^admin_list_events$"))
    application.add_handler(CallbackQueryHandler(admin_event_detail, pattern="^event_detail_"))
    application.add_handler(CallbackQueryHandler(admin_event_delete, pattern="^event_delete_"))
    application.add_handler(CallbackQueryHandler(admin_event_toggle, pattern="^event_toggle_"))
    
    # 방 삭제 콜백 핸들러 (delete_room_ 패턴)
    application.add_handler(CallbackQueryHandler(admin_delete_room_confirm, pattern="^delete_room_"))

    # 버튼(callback_query) 핸들러 등록 (일반 유저용)
    application.add_handler(CallbackQueryHandler(button_callback))

    # 에러 핸들러 등록
    application.add_error_handler(error_handler)

    print("=" * 50)
    print("🤖 봇이 시작되었습니다!")
    print("=" * 50)
    print("등록된 핸들러:")
    print("  - 기본 명령어: /start, /help, /stats, /debug_token")
    print("  - 관리자 명령어: /admin")
    print("  - ConversationHandlers: 방 생성, 방 수정, 배너 생성, 인원 수 업데이트, 쿠폰 발급, 쿠폰 사용 처리, 이벤트 작성")
    print("  - 콜백 핸들러: admin_*, delete_room_*")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
