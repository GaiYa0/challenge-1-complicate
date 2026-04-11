"""存储与数据分层枚举（数据湖 raw / clean / feature）。"""

from enum import Enum


class DataLayer(str, Enum):
    RAW = "raw"
    CLEAN = "clean"
    FEATURE = "feature"


class LifecycleTier(str, Enum):
    """文件生命周期：热 / 温 / 冷（由定时任务迁移）。"""

    HOT = "hot"
    WARM = "warm"
    COLD = "cold"


class ArchiveFormat(str, Enum):
    NONE = "none"
    GZIP_CSV = "gzip_csv"
    PARQUET = "parquet"
