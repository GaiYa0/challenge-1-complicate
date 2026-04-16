"""
异步流水线任务 I/O 结构（仅数据契约，不含业务实现）。

所有任务必须携带 case_id / user_id 以便审计与缓存隔离。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineCleanTaskInput(BaseModel):
    """数据清洗任务输入。"""

    case_id: int
    user_id: int
    file_id: int
    analysis_task_public_id: str
    options: dict[str, Any] = Field(default_factory=dict)


class PipelineCleanTaskOutput(BaseModel):
    """数据清洗任务输出（结构化摘要，供后续任务引用）。"""

    case_id: int
    file_id: int
    clean_summary: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: dict[str, Any] = Field(default_factory=dict)


class FeatureExtractTaskInput(BaseModel):
    """特征提取任务输入。"""

    case_id: int
    user_id: int
    file_id: int
    analysis_task_public_id: str
    depends_on_clean_ref: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class FeatureExtractTaskOutput(BaseModel):
    """特征提取任务输出。"""

    case_id: int
    file_id: int
    feature_bundle: dict[str, Any] = Field(default_factory=dict)


class GraphBuildTaskInput(BaseModel):
    """图构建任务输入（投影到 Neo4j 或中间图结构）。"""

    case_id: int
    user_id: int
    analysis_task_public_id: str
    source_file_ids: list[int] = Field(default_factory=list)
    feature_refs: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class GraphBuildTaskOutput(BaseModel):
    """图构建任务输出。"""

    case_id: int
    projection_ref: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, Any] = Field(default_factory=dict)


class ClueGenerateTaskInput(BaseModel):
    """线索生成任务输入。"""

    case_id: int
    user_id: int
    analysis_task_public_id: str
    subject_keys: list[str] = Field(default_factory=list)
    feature_refs: dict[str, Any] | None = None
    graph_refs: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ClueGenerateTaskOutput(BaseModel):
    """线索生成任务输出。"""

    case_id: int
    clue_ids: list[int] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
