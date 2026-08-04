from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from empriority.connectors.sidra import SidraQuery


class SidraIndicatorConfig(BaseModel):
    source: Literal["sidra"]
    description: str
    dimension: str
    output: str
    table: int = Field(gt=0)
    territorial_level: int = Field(gt=0)
    territories: str = "all"
    variables: str = "all"
    periods: str = "last"
    classifications: dict[int, str] = Field(default_factory=dict)

    def to_query(self) -> SidraQuery:
        return SidraQuery(
            table=self.table,
            territorial_level=self.territorial_level,
            territories=self.territories,
            variables=self.variables,
            periods=self.periods,
            classifications=self.classifications,
        )


class IndicatorCatalog(BaseModel):
    indicators: dict[str, SidraIndicatorConfig]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.indicators))

    def get(self, name: str) -> SidraIndicatorConfig:
        try:
            return self.indicators[name]
        except KeyError as exc:
            available = ", ".join(self.names()) or "none"
            raise KeyError(f"Unknown indicator '{name}'. Available: {available}") from exc


def load_indicator_catalog(path: str | Path = "config/indicators.yml") -> IndicatorCatalog:
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Indicator catalog not found: {catalog_path}")

    with catalog_path.open("r", encoding="utf-8") as stream:
        raw: dict[str, Any] = yaml.safe_load(stream) or {}
    return IndicatorCatalog.model_validate(raw)
