from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class CriterionConfig(BaseModel):
    column: str
    label: str
    direction: Literal["benefit", "cost"] = "benefit"
    dimension: str


class ModelConfig(BaseModel):
    id_columns: list[str] = Field(min_length=1)
    alpha: float = Field(default=0.5, ge=0, le=1)
    criteria: list[CriterionConfig] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_columns(self) -> ModelConfig:
        columns = [item.column for item in self.criteria]
        if len(columns) != len(set(columns)):
            raise ValueError("Criterion columns must be unique")
        return self

    @property
    def criterion_columns(self) -> list[str]:
        return [item.column for item in self.criteria]

    @property
    def directions(self) -> dict[str, str]:
        return {item.column: item.direction for item in self.criteria}


def load_model_config(path: str | Path = "config/criteria.yml") -> ModelConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Criteria configuration not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream) or {}
    return ModelConfig.model_validate(raw)
