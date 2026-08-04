from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pandas as pd


class MUNICConnector:
    """Download and read the official IBGE MUNIC workbook."""

    def __init__(self, base_url: str, timeout: float = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def workbook_url(self, year: int) -> str:
        return f"{self.base_url}/{year}/Base_de_Dados/Base_MUNIC_{year}.xlsx"

    def fetch_workbook(self, year: int = 2023) -> bytes:
        url = self.workbook_url(year)
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
        if not response.content.startswith(b"PK"):
            raise ValueError("MUNIC response is not a valid XLSX workbook.")
        return response.content

    def save_workbook(self, destination: str | Path, year: int = 2023) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.fetch_workbook(year))
        return path

    def read_sheets(self, year: int = 2023) -> dict[str, pd.DataFrame]:
        content = self.fetch_workbook(year)
        return pd.read_excel(BytesIO(content), sheet_name=None, dtype=str)

    def read_inventory(self, year: int = 2023) -> pd.DataFrame:
        sheets = self.read_sheets(year)
        rows: list[dict[str, Any]] = []
        for sheet_name, frame in sheets.items():
            rows.append(
                {
                    "sheet": sheet_name,
                    "rows": len(frame),
                    "columns": len(frame.columns),
                    "column_names": " | ".join(str(column) for column in frame.columns),
                }
            )
        return pd.DataFrame(rows)

    def filter_state(
        self,
        frame: pd.DataFrame,
        state_ibge_code: int,
    ) -> pd.DataFrame:
        """Filter a MUNIC sheet to one state using common IBGE identifiers."""
        candidates = (
            "CodMun",
            "Cod_Munic",
            "Código do Município",
            "Codigo do Municipio",
            "codigo_ibge",
            "UF",
            "CodUF",
        )
        column = next((candidate for candidate in candidates if candidate in frame.columns), None)
        if column is None:
            return frame.copy()

        values = frame[column].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        state = str(state_ibge_code)
        if values.str.len().ge(6).any():
            mask = values.str.startswith(state)
        else:
            mask = values.eq(state)
        return frame.loc[mask].copy()
