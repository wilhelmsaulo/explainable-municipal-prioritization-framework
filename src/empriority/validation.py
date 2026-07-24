from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MunicipalityValidationResult:
    expected_count: int
    observed_count: int
    duplicated_codes: tuple[str, ...]
    missing_codes: int

    @property
    def is_valid(self) -> bool:
        return (
            self.observed_count == self.expected_count
            and not self.duplicated_codes
            and self.missing_codes == 0
        )


def validate_municipalities(
    frame: pd.DataFrame,
    expected_count: int,
) -> MunicipalityValidationResult:
    required = {"municipality_code", "municipality_name"}
    missing_columns = required.difference(frame.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    codes = frame["municipality_code"]
    duplicated = tuple(sorted(codes[codes.duplicated()].astype(str).unique()))
    missing_codes = int(codes.isna().sum() + codes.astype("string").str.strip().eq("").sum())

    return MunicipalityValidationResult(
        expected_count=expected_count,
        observed_count=len(frame),
        duplicated_codes=duplicated,
        missing_codes=missing_codes,
    )
