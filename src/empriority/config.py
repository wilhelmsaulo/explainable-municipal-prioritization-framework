from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl


class ProjectConfig(BaseModel):
    name: str
    country: str = "BR"
    state_code: str = Field(min_length=2, max_length=2)
    state_ibge_code: int
    expected_municipalities: int = Field(gt=0)


class RuntimeConfig(BaseModel):
    request_timeout_seconds: float = Field(default=30, gt=0)
    cache_enabled: bool = True
    cache_directory: Path = Path("data/cache")
    output_directory: Path = Path("data/processed")


class SourceConfig(BaseModel):
    enabled: bool = True
    base_url: HttpUrl


class SourcesConfig(BaseModel):
    ibge_localities: SourceConfig
    sidra: SourceConfig
    munic: SourceConfig


class Settings(BaseModel):
    project: ProjectConfig
    runtime: RuntimeConfig
    sources: SourcesConfig


def load_settings(path: str | Path = "config/project.yml") -> Settings:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream) or {}

    return Settings.model_validate(raw)
