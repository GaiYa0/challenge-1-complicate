"""user-service 配置：仅 user 库与 JWT / 内部调用令牌。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.user", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "user-service"
    DATABASE_URL: str = Field(
        default="postgresql://user:password@localhost:5432/user_db",
        description="仅 user_db，禁止指向其他业务库",
    )
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_MINUTES: int = 60
    INTERNAL_API_TOKEN: str = Field(
        default="change-internal-token",
        description="file/data/model 等服务间调用校验",
    )
    FILE_SERVICE_URL: str = Field(
        default="http://127.0.0.1:8002",
        description="HTTP 调用 file-service（禁止直连 file_db）",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
