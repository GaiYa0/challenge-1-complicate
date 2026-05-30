"""
应用配置：pydantic-settings + 环境变量 + .env.dev / .env.prod
"""

import logging
import os
import warnings
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_log = logging.getLogger(__name__)


def _env_file_candidates() -> tuple[str, ...]:
    """按 APP_ENV（默认 dev）加载 .env.dev / .env.prod，并回退 .env。"""
    env = os.getenv("APP_ENV", "dev").strip().lower() or "dev"
    return (f".env.{env}", ".env")


class Settings(BaseSettings):
    """全部从环境变量 / env 文件读取；未提供时使用本地开发默认值。"""

    model_config = SettingsConfigDict(
        env_file=_env_file_candidates(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "challenge_demo"
    DEBUG: bool = False
    CORS_ORIGINS: str = Field(
        default="",
        description="逗号分隔的前端 Origin；非 DEBUG 且非空时启用 CORS（生产跨域）",
    )

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "user"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "dbname"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = Field(default=False, description="生产环境应设为 true 以启用 TLS")

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_MINUTES: int = 60

    # Celery
    CELERY_BROKER_URL: str = Field(
        default="",
        description="为空则启动时用 redis://REDIS_HOST:REDIS_PORT/0",
    )
    CELERY_RESULT_BACKEND: str = Field(default="")

    # Neo4j（图谱 / analyze:graph 依赖；与 DB 等一并走 env 文件）
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "dev032500"

    # Kafka / Redpanda（事件驱动；KAFKA_ENABLED=false 时不连接）
    KAFKA_ENABLED: bool = False
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:19092"
    KAFKA_CLIENT_ID: str = "challenge_demo"
    KAFKA_CONSUMER_GROUP: str = "challenge-demo-pipeline"
    KAFKA_AUTO_ACTIVATE_MODEL: bool = Field(
        default=False,
        description="model-trained 消费者是否自动将新版本设为 active（生产慎用）",
    )
    KAFKA_CONSUMER_MAX_RETRIES: int = 3
    KAFKA_CONSUMER_RETRY_BASE_SEC: float = 1.0
    KAFKA_UPLOAD_FALLBACK_CELERY: bool = Field(
        default=True,
        description="KAFKA_ENABLED=false 时，上传后是否直接 Celery 投递清洗（无 Kafka 的本地开发）",
    )

    # 生产降级：压力过大时关闭非核心能力（如图谱）
    DEGRADED: bool = Field(default=False, description="true 时对部分路由返回 503 降级")
    DEGRADE_GRAPH: bool = Field(default=True, description="DEGRADED=true 时是否禁用 /graph")

    # 演示 / 性能：无 Neo4j 时仍可展示关系页；图谱 Redis 缓存
    DEMO_MODE: bool = Field(
        default=False,
        description="true 时 /analysis/graph 与 /analysis/degree 返回内置 mock，跳过 Neo4j",
    )
    GRAPH_VIZ_CACHE_TTL_SEC: int = Field(
        default=45,
        ge=5,
        le=3600,
        description="Redis 中分析页关系图 / 出度缓存 TTL（秒）",
    )
    GRAPH_NODE_CAP: int = Field(
        default=100,
        ge=10,
        le=500,
        description="分析页关系图最多展示的节点数（边查询后再裁剪）",
    )

    # 生命周期 / 成本
    LIFECYCLE_DELETE_WARM_AFTER_COLD: bool = Field(
        default=False,
        description="冷迁移后是否删除标准桶对象（省存储；生产需确认可再从冷还原）",
    )
    LIFECYCLE_COLD_ARCHIVE_BATCH: int = Field(default=30, ge=1, le=500)
    COST_METRICS_ENABLED: bool = Field(default=True, description="是否异步写入 cost_metrics 表")

    COMPLIANCE_EXPORT_APPROVAL_REQUIRED: bool = Field(
        default=True,
        description="非 admin 用户生成报告是否必须关联已审批的 export_request",
    )

    # Celery 调度 / 隔离
    CELERY_MAX_CONCURRENT_PER_USER: int = Field(
        default=8,
        ge=1,
        le=64,
        description="单用户可同时执行的业务任务数上限（worker 侧槽位）",
    )
    CELERY_TASK_MAX_RETRIES: int = Field(
        default=5,
        ge=0,
        le=20,
        description="带 QuotaTrackedTask 的默认可重试次数上界（任务装饰器可覆盖）",
    )

    # 限流
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = Field(
        default=600,
        ge=30,
        le=100000,
        description="单用户每分钟全局请求数上限（GET 轮询/ID-幂等路径可豁免）",
    )
    RATE_LIMIT_BURST_BUCKET_SEC: int = Field(
        default=10,
        ge=2,
        le=60,
        description="突发窗口长度（秒）；同时限制短时峰值",
    )
    RATE_LIMIT_BURST_PER_BUCKET: int = Field(
        default=120,
        ge=10,
        le=10000,
        description="突发窗口内的请求数上限（防止轮询风暴）",
    )
    RATE_LIMIT_EXEMPT_PREFIXES: str = Field(
        default="/task/,/auth/me,/live,/ready,/metrics",
        description="逗号分隔；以此为前缀（或完全匹配 /auth/me 等）的路径豁免全局限流",
    )

    # 反向代理 / 请求 ID 安全
    TRUSTED_PROXY_IPS: str = Field(
        default="127.0.0.1/32,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16",
        description="逗号分隔 CIDR；仅来自这些对端的 X-Forwarded-For / X-Request-ID 被采信",
    )
    REQUEST_ID_MAX_LEN: int = Field(default=128, ge=16, le=256)

    # 导入识别
    IMPORT_MATCH_NAME_WEIGHT: float = Field(default=0.7, ge=0.0, le=1.0)
    IMPORT_MATCH_CONTENT_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    IMPORT_MATCH_MIN_SCORE: float = Field(default=55.0, ge=0.0, le=100.0)
    IMPORT_MAPPING_REUSE_MIN_SIMILARITY: float = Field(default=80.0, ge=0.0, le=100.0)

    # 报告保留
    REPORT_RETENTION_DAYS: int = Field(
        default=30,
        ge=1,
        le=365,
        description="MinIO reports 桶按 last_modified 清理的保留天数",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{quote_plus(self.DB_USER)}:{quote_plus(self.DB_PASSWORD)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.CORS_ORIGINS.strip():
            return []
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

    @property
    def rate_limit_exempt_prefixes(self) -> tuple[str, ...]:
        raw = (self.RATE_LIMIT_EXEMPT_PREFIXES or "").strip()
        if not raw:
            return tuple()
        return tuple(x.strip() for x in raw.split(",") if x.strip())


_WEAK_DEFAULTS = {
    "JWT_SECRET": "change-me-in-production",
    "DB_PASSWORD": "password",
    "NEO4J_PASSWORD": "dev032500",
    "MINIO_ACCESS_KEY": "minioadmin",
    "MINIO_SECRET_KEY": "minioadmin",
}


def _warn_weak_defaults(s: Settings) -> None:
    """非 DEBUG 模式下，检测到弱默认值时发出警告。"""
    if s.DEBUG:
        return
    for attr, weak in _WEAK_DEFAULTS.items():
        if getattr(s, attr, None) == weak:
            msg = f"SECURITY: {attr} is using the default weak value — override via env before production"
            _log.warning(msg)
            warnings.warn(msg, stacklevel=3)


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置（测试可用 get_settings.cache_clear()）。"""
    s = Settings()
    _warn_weak_defaults(s)
    return s


# --- 与路径/缓存相关的固定项（保持调用方 import 不变）---
UPLOAD_DIR = Path("uploads")
MODEL_SAVE_PATH = Path("models") / "model.pkl"
CACHE_TTL_TEST = 60
CACHE_TTL_ANALYZE = 120

# --- 上传与安全 ---
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = (".csv", ".json", ".xls", ".xlsx")

# 保留模块级常量以兼容既有 import；真实值取自 Settings 动态读。
RATE_LIMIT_REQUESTS_PER_MINUTE = 600
