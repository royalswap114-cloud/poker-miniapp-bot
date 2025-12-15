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

    # WebApp 버튼 (커스텀 미니앱 UI 열기 - WEBAPP_URL)
    webapp_button = InlineKeyboardButton(
        text="🎰 TTPOKER 입장하기",
        web_app=WebAppInfo(url=WEBAPP_URL),  # 텔레그램 내 WebView 로 커스텀 미니앱 열기
    )

    # 통계용: 게임 시작 버튼 (callback query)
    start_game_button = InlineKeyboardButton(
        text="▶️ 게임 시작하기",
        callback_data="start_game",
    )

    keyboard = InlineKeyboardMarkup(
        [
            [webapp_button],
            [start_game_button],
        ]
    )

    welcome_text = (
        "안녕하세요! PokerNow 미니앱 연동 봇입니다.\n\n"
        "아래 버튼을 사용해 보세요:\n"
        "🃏 <b>PokerNow 미니앱 열기</b> - 텔레그램 안에서 pokernow.club 을 WebApp 으로 엽니다.\n"
        "▶️ <b>게임 시작하기</b> - 게임 시작 알림 + 플레이 횟수 기록.\n\n"
        "또는 /stats 로 본인 통계를 확인할 수 있습니다.\n"
        "도움말: /help"
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

    # 일반 유저용 게임 시작 버튼
    if data == "start_game":
        # 통계 증가
        increase_play_count(user.id, user.username)

        # 사용자에게 알림 메시지
        msg = (
            "✅ 게임을 시작했습니다!\n"
            "PokerNow 방을 생성하거나 입장한 후 플레이를 즐겨주세요.\n\n"
            f"현재까지 기록된 플레이 횟수: {user_stats[user.id]['play_count']} 회"
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
        build_banner_create_conversation,
    )

    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(build_admin_create_room_conversation())
    application.add_handler(build_banner_create_conversation())
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))

    # 버튼(callback_query) 핸들러 등록 (일반 유저용)
    application.add_handler(CallbackQueryHandler(button_callback))

    # 에러 핸들러 등록
    application.add_error_handler(error_handler)

    print("🤖 봇이 시작되었습니다... Ctrl+C 로 종료할 수 있습니다.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
