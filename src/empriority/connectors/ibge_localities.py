from __future__ import annotations

from typing import Any

import httpx
import pandas as pd


class IBGELocalitiesConnector:
    """Client for the official IBGE Localities API."""

    def __init__(self, base_url: str, timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch_municipalities(self, state_code: str) -> pd.DataFrame:
        url = f"{self.base_url}/estados/{state_code}/municipios"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            payload: list[dict[str, Any]] = response.json()

        records = [self._normalize(item) for item in payload]
        frame = pd.DataFrame.from_records(records)
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "municipality_code",
                    "municipality_name",
                    "state_code",
                    "state_name",
                    "region_code",
                    "region_name",
                ]
            )
        return frame.sort_values("municipality_code").reset_index(drop=True)

    @staticmethod
    def _normalize(item: dict[str, Any]) -> dict[str, Any]:
        immediate = item.get("regiao-imediata") or {}
        intermediate = immediate.get("regiao-intermediaria") or {}
        state = intermediate.get("UF") or {}
        region = state.get("regiao") or {}
        return {
            "municipality_code": str(item["id"]),
            "municipality_name": item["nome"],
            "state_code": state.get("sigla"),
            "state_name": state.get("nome"),
            "region_code": str(region.get("id")) if region.get("id") is not None else None,
            "region_name": region.get("nome"),
        }
