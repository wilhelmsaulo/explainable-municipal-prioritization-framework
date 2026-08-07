from __future__ import annotations

from pathlib import Path

import pandas as pd

YES_VALUES = {"sim", "1", "1.0", "true", "yes"}
NO_VALUES = {"nao", "não", "0", "0.0", "false", "no"}


def _binary(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    result = pd.Series(pd.NA, index=series.index, dtype="Int64")
    result.loc[normalized.isin(YES_VALUES)] = 1
    result.loc[normalized.isin(NO_VALUES)] = 0
    return result


def _municipal_id_columns(frame: pd.DataFrame) -> tuple[str, str]:
    code = next(
        (
            column
            for column in frame.columns
            if str(column).replace(" ", "").lower() in {"codmun", "codmunic"}
        ),
        None,
    )
    name = next(
        (
            column
            for column in frame.columns
            if str(column).replace(" ", "").lower() in {"mun", "descmun"}
        ),
        None,
    )
    if code is None or name is None:
        raise ValueError("MUNIC extract must contain municipality code and name columns.")
    return code, name


def extract_munic_2023_institutional_indicators(
    women_policy_path: str | Path,
    public_security_path: str | Path,
    human_rights_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Extract the institutional indicators previously defined for the project."""
    women = pd.read_csv(women_policy_path, dtype=str)
    security = pd.read_csv(public_security_path, dtype=str)
    rights = pd.read_csv(human_rights_path, dtype=str)

    women_code, women_name = _municipal_id_columns(women)
    security_code, _ = _municipal_id_columns(security)
    rights_code, _ = _municipal_id_columns(rights)

    base = women[[women_code, women_name, "MPPM01"]].copy()
    base = base.rename(
        columns={
            women_code: "municipality_code",
            women_name: "municipality",
            "MPPM01": "women_policy_body_exists_raw",
        }
    )
    base["municipality_code"] = (
        base["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    base["women_policy_body_exists"] = _binary(base["women_policy_body_exists_raw"])

    security_local = security[[security_code, "MSEG168"]].copy()
    security_local = security_local.rename(
        columns={
            security_code: "municipality_code",
            "MSEG168": "specialized_women_police_station_raw",
        }
    )
    security_local["municipality_code"] = (
        security_local["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    security_local["specialized_women_police_station"] = _binary(
        security_local["specialized_women_police_station_raw"]
    )

    rights_local = rights[[rights_code, "MDHU083", "MDHU571"]].copy()
    rights_local = rights_local.rename(
        columns={
            rights_code: "municipality_code",
            "MDHU083": "programs_actions_for_women_raw",
            "MDHU571": "human_rights_protection_women_raw",
        }
    )
    rights_local["municipality_code"] = (
        rights_local["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    rights_local["programs_actions_for_women"] = _binary(
        rights_local["programs_actions_for_women_raw"]
    )
    rights_local["human_rights_protection_women"] = _binary(
        rights_local["human_rights_protection_women_raw"]
    )

    result = base.merge(security_local, on="municipality_code", how="left").merge(
        rights_local,
        on="municipality_code",
        how="left",
    )
    result["campaigns_against_violence_women"] = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Int64",
    )
    result["campaigns_indicator_status"] = "not_available_in_munic_2023_questionnaire"

    binary_columns = [
        "specialized_women_police_station",
        "programs_actions_for_women",
        "women_policy_body_exists",
        "human_rights_protection_women",
    ]
    result["institutional_score_available_4"] = result[binary_columns].sum(axis=1, min_count=1)
    result["institutional_coverage"] = result[binary_columns].notna().sum(axis=1)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.sort_values("municipality_code").to_csv(path, index=False, encoding="utf-8")
    return path
