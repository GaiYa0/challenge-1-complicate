"""
Docker / 本地统一入口：uvicorn main:app（应用定义在 backend.app.main）。
"""

from backend.app.main import app

__all__ = ["app"]
