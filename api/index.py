"""
Vercel entry point for FastAPI app.

Vercel 의 Python 서버리스 함수는 이 파일을 진입점으로 사용합니다.
여기서는 webapp.app 모듈에서 FastAPI 인스턴스(app)를 가져와서 export 합니다.
"""

from webapp.app import app  # FastAPI 인스턴스

# Vercel 이 인식할 핸들러 이름 (명시적으로 한 번 더 바인딩)
app = app

