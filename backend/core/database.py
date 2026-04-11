"""ORM 基类；引擎与 SessionLocal 在 main lifespan 中创建并挂到 app.state。"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
