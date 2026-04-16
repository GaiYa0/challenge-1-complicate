"""
服务层边界（Protocol）：仅方法签名与类型，便于替换实现与单测。

现有实现位于 backend/app/services/*.py，逐步与下列 Port 对齐；新代码应优先依赖 Protocol。
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session


class FileServicePort(Protocol):
    """文件元数据、对象存储、与案件绑定（case_files）。"""

    def register_upload(
        self,
        db: Session,
        *,
        user_id: int,
        case_id: int,
        raw_filename: str,
        content: bytes,
        dataset: str,
        version: str,
        role: str | None,
    ) -> Any: ...

    def list_files_for_case(self, db: Session, *, case_id: int, user_id: int) -> list[Any]: ...

    def resolve_readable_file(self, db: Session, *, case_id: int, filename: str, user_id: int) -> Any: ...

    def bind_existing_file_to_case(
        self, db: Session, *, case_id: int, file_id: int, user_id: int, role: str | None
    ) -> Any: ...


class DataPipelineServicePort(Protocol):
    """标准化数据流水线：读入 → 清洗摘要 → 特征占位（不实现具体算法）。"""

    def run_pipeline_for_artifact(
        self,
        db: Session,
        *,
        case_id: int,
        file_id: int,
        user_id: int,
    ) -> dict[str, Any]: ...

    def build_clean_summary(self, *, pipeline_result: dict[str, Any]) -> dict[str, Any]: ...


class ClueServicePort(Protocol):
    """线索 CRUD、按案件/人物查询、与 analysis_task 关联。"""

    def list_clues(
        self,
        db: Session,
        *,
        case_id: int,
        user_id: int,
        subject_key: str | None,
    ) -> list[Any]: ...

    def get_clue(self, db: Session, *, case_id: int, clue_id: int, user_id: int) -> Any | None: ...

    def create_clue_placeholder(
        self,
        db: Session,
        *,
        case_id: int,
        user_id: int,
        payload: dict[str, Any],
    ) -> Any: ...

    def attach_clue_to_analysis_task(
        self,
        db: Session,
        *,
        clue_id: int,
        analysis_task_id: int,
    ) -> None: ...


class AnalysisServicePort(Protocol):
    """分析任务：创建领域任务记录、投递 Celery、查询状态与结果引用。"""

    def enqueue_analysis(
        self,
        db: Session,
        *,
        case_id: int,
        user_id: int,
        task_type: str,
        input_payload: dict[str, Any],
    ) -> Any: ...

    def get_task_by_public_id(
        self, db: Session, *, case_id: int, public_id: str, user_id: int
    ) -> Any | None: ...

    def list_tasks_for_case(
        self, db: Session, *, case_id: int, user_id: int, status: str | None
    ) -> list[Any]: ...


class GraphServicePort(Protocol):
    """图数据：Neo4j 查询、案件投影、可视化子图数据构建（不含具体 Cypher 业务）。"""

    def build_visualization_for_case(
        self,
        db: Session,
        *,
        case_id: int,
        user_id: int,
        edge_limit: int,
    ) -> dict[str, Any]: ...

    def request_projection_job(
        self,
        db: Session,
        *,
        case_id: int,
        user_id: int,
        options: dict[str, Any] | None,
    ) -> Any: ...
