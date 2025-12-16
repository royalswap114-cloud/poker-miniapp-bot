"""
bot/utils.py

공통 유틸리티 함수 모듈.
- 관리자 권한 체크
- 기타 헬퍼 함수
"""

from __future__ import annotations

import os
from typing import Set

from dotenv import load_dotenv

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


# 전역 ADMIN_IDS 로드
ADMIN_IDS = _parse_admin_ids(os.getenv("ADMIN_IDS"))


def is_admin(user_id: int) -> bool:
    """
    해당 user_id 가 ADMIN_IDS 에 포함되어 있는지 확인.
    """
    return user_id in ADMIN_IDS


