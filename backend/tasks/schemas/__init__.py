"""Celery 任务 payload 的 Pydantic 模型（结构-only）。"""

from backend.tasks.schemas.pipeline_io import (
    ClueGenerateTaskInput,
    ClueGenerateTaskOutput,
    FeatureExtractTaskInput,
    FeatureExtractTaskOutput,
    GraphBuildTaskInput,
    GraphBuildTaskOutput,
    PipelineCleanTaskInput,
    PipelineCleanTaskOutput,
)

__all__ = [
    "ClueGenerateTaskInput",
    "ClueGenerateTaskOutput",
    "FeatureExtractTaskInput",
    "FeatureExtractTaskOutput",
    "GraphBuildTaskInput",
    "GraphBuildTaskOutput",
    "PipelineCleanTaskInput",
    "PipelineCleanTaskOutput",
]
