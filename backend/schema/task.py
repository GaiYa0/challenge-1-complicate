from typing import Any

from pydantic import BaseModel


class TaskEnqueueData(BaseModel):
    task_id: str


class TaskStatusData(BaseModel):
    state: str


class TaskResultData(BaseModel):
    state: str
    result: Any = None
