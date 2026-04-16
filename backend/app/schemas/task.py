from typing import Any

from pydantic import BaseModel, Field


class TaskEnqueueData(BaseModel):
    task_id: str


class TaskStatusData(BaseModel):
    state: str


class TaskResultData(BaseModel):
    state: str
    result: Any = None


class TaskBatchItem(BaseModel):
    task_id: str
    state: str
    result: Any = None
    error: str | None = None


class TaskBatchData(BaseModel):
    items: list[TaskBatchItem] = Field(default_factory=list)
