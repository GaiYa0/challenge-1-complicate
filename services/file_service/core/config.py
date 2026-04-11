from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FileSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.file", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "file-service"
    INTERNAL_API_TOKEN: str = Field(default="change-internal-token")
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="localhost:19092")
    KAFKA_CLIENT_ID: str = "file-service"


@lru_cache
def get_file_settings() -> FileSettings:
    return FileSettings()
