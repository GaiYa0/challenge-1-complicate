"""
Docker / 本地统一入口：uvicorn main:app（应用定义在 backend.main）。
"""

from backend.main import app

__all__ = ["app"]
