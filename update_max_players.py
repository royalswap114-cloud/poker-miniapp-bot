"""
update_max_players.py

기존 방들의 max_players 값을 10으로 업데이트하는 마이그레이션 스크립트.

사용법:
    python update_max_players.py

주의:
    - 실행 전에 데이터베이스 백업 권장
    - 모든 방의 max_players가 9인 경우에만 10으로 업데이트
"""

from bot.database import SessionLocal, Room

db = SessionLocal()

try:
    # 모든 방 조회
    rooms = db.query(Room).all()
    
    if not rooms:
        print("업데이트할 방이 없습니다.")
    else:
        updated_count = 0
        for room in rooms:
            # max_players가 9인 경우에만 10으로 업데이트
            if room.max_players == 9:
                room.max_players = 10
                updated_count += 1
                print(f"Room {room.id} ({room.room_name}): max_players 9 → 10")
        
        if updated_count > 0:
            db.commit()
            print(f"\n✅ 총 {updated_count}개 방의 max_players가 10으로 업데이트되었습니다.")
        else:
            print(f"\nℹ️  업데이트할 방이 없습니다. (모든 방의 max_players가 이미 10 이상입니다.)")
    
except Exception as e:
    print(f"❌ 오류 발생: {e}")
    db.rollback()
finally:
    db.close()

