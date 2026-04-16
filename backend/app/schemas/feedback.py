from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FeedbackIn(BaseModel):
    filename: str
    label: Literal[0, 1] | None = Field(
        default=None,
        description="兼容旧接口：1 视为预测正确，0 为错误",
    )
    is_correct: bool | None = Field(default=None, description="显式标注预测是否正确")
    prediction: int | None = Field(default=None, description="当时的模型预测值")
    model_name: str | None = None
    model_version: str | None = None
    entity_id: int | None = None

    @model_validator(mode="after")
    def _label_or_correct(self) -> FeedbackIn:
        if self.is_correct is None and self.label is None:
            raise ValueError("必须提供 is_correct 或 label")
        return self
