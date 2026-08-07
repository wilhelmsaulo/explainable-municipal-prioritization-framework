from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pandas as pd


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def _column(frame: pd.DataFrame, *names: str) -> str | None:
    normalized = {_norm(column).replace(" ", "_"): column for column in frame.columns}
    for name in names:
        found = normalized.get(_norm(name).replace(" ", "_"))
        if found is not None:
            return found
    return None


def _member(archive: zipfile.ZipFile, prefix: str) -> str:
    matches = [
        name
        for name in archive.namelist()
        if Path(name).name.lower().startswith(prefix.lower()) and name.lower().endswith(".csv")
    ]
    if not matches:
        raise RuntimeError(f"CNES archive has no table beginning with {prefix!r}.")
    return sorted(matches)[0]


def _read_member(archive_path: Path, member: str, **kwargs: object) -> pd.DataFrame:
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as stream:
        return pd.read_csv(
            stream,
            sep=";",
            encoding="latin1",
            low_memory=False,
            **kwargs,
        )


def _chunks(archive_path: Path, member: str, chunksize: int = 250_000) -> Iterator[pd.DataFrame]:
    with zipfile.ZipFile(archive_path) as archive, archive.open(member) as stream:
        yield from pd.read_csv(
            stream,
            sep=";",
            encoding="latin1",
            low_memory=False,
            chunksize=chunksize,
        )


def _classify_profession(description: object, cbo: object) -> str | None:
    text = _norm(description)
    code = re.sub(r"\D", "", str(cbo or ""))

    if "psicolog" in text or code.startswith("2515"):
        return "psychologists"
    if "assistente social" in text or code.startswith("2516"):
        return "social_workers"
    if "enfermeir" in text or code.startswith("2235"):
        return "nurses"
    if "medico" in text or code.startswith("225"):
        return "physicians"
    return None


def build_cnes_professional_indicators(
    archive_path: str | Path,
    establishments_path: str | Path,
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    archive_path = Path(archive_path)
    establishments_path = Path(establishments_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    if not archive_path.exists():
        raise FileNotFoundError(archive_path)
    if not establishments_path.exists():
        raise FileNotFoundError(establishments_path)

    establishments = pd.read_csv(establishments_path, low_memory=False)
    unit_column = _column(establishments, "CO_UNIDADE", "CO_CNES", "CNES", "codigo_cnes")
    municipality_column = _column(
        establishments,
        "CO_MUNICIPIO_GESTOR",
        "CO_MUNICIPIO",
        "CODUFMUN",
        "IBGE",
        "codigo_municipio",
    )
    if unit_column is None or municipality_column is None:
        raise RuntimeError(
            "The Pará establishment snapshot lacks unit or municipality codes: "
            f"{list(establishments.columns)}"
        )

    unit_map = establishments[[unit_column, municipality_column]].copy()
    unit_map.columns = ["unit_code", "municipality_code"]
    unit_map["unit_code"] = (
        unit_map["unit_code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    )
    unit_map["municipality_code"] = (
        unit_map["municipality_code"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    )
    unit_map = unit_map.drop_duplicates("unit_code")
    pa_units = set(unit_map["unit_code"])

    with zipfile.ZipFile(archive_path) as archive:
        workload_member = _member(archive, "tbCargaHorariaSus")
        activity_member = _member(archive, "tbAtividadeProfissional")

    activities = _read_member(archive_path, activity_member)
    cbo_column = _column(activities, "CO_CBO")
    description_column = _column(activities, "DS_ATIVIDADE_PROFISSIONAL")
    if cbo_column is None or description_column is None:
        raise RuntimeError(
            f"CNES CBO dictionary has unexpected columns: {list(activities.columns)}"
        )

    cbo_dictionary = activities[[cbo_column, description_column]].copy()
    cbo_dictionary.columns = ["cbo", "profession_description"]
    cbo_dictionary["cbo"] = cbo_dictionary["cbo"].astype(str).str.replace(r"\.0$", "", regex=True)
    cbo_dictionary = cbo_dictionary.drop_duplicates("cbo")

    selected: list[pd.DataFrame] = []
    scanned = 0
    for chunk in _chunks(archive_path, workload_member):
        scanned += len(chunk)
        unit = _column(chunk, "CO_UNIDADE")
        professional = _column(chunk, "CO_PROFISSIONAL_SUS")
        cbo = _column(chunk, "CO_CBO")
        amb = _column(chunk, "QT_CARGA_HORARIA_AMBULATORIAL")
        other = _column(chunk, "QT_CARGA_HORARIA_OUTROS")
        hospital = _column(chunk, "QT_CARGA_HOR_HOSP_SUS")
        if unit is None or professional is None or cbo is None:
            raise RuntimeError(f"CNES workload table has unexpected columns: {list(chunk.columns)}")

        local = pd.DataFrame(
            {
                "unit_code": chunk[unit]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.zfill(7),
                "professional_id": chunk[professional]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True),
                "cbo": chunk[cbo].astype(str).str.replace(r"\.0$", "", regex=True),
                "hours_ambulatory": pd.to_numeric(chunk[amb], errors="coerce").fillna(0)
                if amb
                else 0,
                "hours_other": pd.to_numeric(chunk[other], errors="coerce").fillna(0)
                if other
                else 0,
                "hours_hospital_sus": pd.to_numeric(chunk[hospital], errors="coerce").fillna(0)
                if hospital
                else 0,
            }
        )
        local = local.loc[local["unit_code"].isin(pa_units)]
        if not local.empty:
            selected.append(local)
        print(
            f"CNES professionals scanned={scanned} pa_rows={sum(len(item) for item in selected)}",
            flush=True,
        )

    if not selected:
        raise RuntimeError(
            "No CNES professional workload records were matched to Pará establishments."
        )

    professionals = pd.concat(selected, ignore_index=True)
    professionals = professionals.merge(unit_map, on="unit_code", how="left")
    professionals = professionals.merge(cbo_dictionary, on="cbo", how="left")
    professionals["profession_group"] = [
        _classify_profession(description, cbo)
        for description, cbo in zip(professionals["profession_description"], professionals["cbo"])
    ]
    professionals = professionals.loc[professionals["profession_group"].notna()].copy()
    professionals["weekly_hours"] = (
        professionals["hours_ambulatory"]
        + professionals["hours_other"]
        + professionals["hours_hospital_sus"]
    )

    # A professional may have multiple establishments or contracts in one municipality.
    # Count each professional once per municipality and category while summing declared workload.
    person_municipality = professionals.groupby(
        ["municipality_code", "profession_group", "professional_id"],
        as_index=False,
    )["weekly_hours"].sum()

    counts = person_municipality.pivot_table(
        index="municipality_code",
        columns="profession_group",
        values="professional_id",
        aggfunc="nunique",
        fill_value=0,
    )
    hours = person_municipality.pivot_table(
        index="municipality_code",
        columns="profession_group",
        values="weekly_hours",
        aggfunc="sum",
        fill_value=0,
    )

    categories = ["physicians", "nurses", "psychologists", "social_workers"]
    result = pd.DataFrame(index=sorted(unit_map["municipality_code"].unique()))
    for category in categories:
        result[f"cnes_{category}"] = counts.get(category, 0)
        result[f"cnes_{category}_weekly_hours"] = hours.get(category, 0.0)
    result = result.fillna(0).reset_index(names="municipality_code")

    count_columns = [f"cnes_{category}" for category in categories]
    for column in count_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    hour_columns = [f"cnes_{category}_weekly_hours" for category in categories]
    result[hour_columns] = result[hour_columns].apply(pd.to_numeric, errors="coerce").fillna(0)

    result["cnes_multidisciplinary_staff_deficit"] = (
        result["cnes_psychologists"].eq(0).astype(int)
        + result["cnes_social_workers"].eq(0).astype(int)
        + result["cnes_nurses"].eq(0).astype(int)
        + result["cnes_physicians"].eq(0).astype(int)
    )

    if len(result) != 144 or result["municipality_code"].nunique() != 144:
        raise AssertionError(
            f"Expected 144 Pará municipalities, got rows={len(result)} "
            f"unique={result['municipality_code'].nunique()}"
        )
    if result[count_columns].sum().sum() == 0:
        raise AssertionError("All CNES professional indicators are zero.")

    indicators_path = output / "cnes_professional_indicators_pa.csv"
    metadata_path = output / "cnes_professional_indicators_pa.metadata.json"
    snapshot_path = output / "cnes_professional_records_pa.csv"

    # Keep a reproducible, non-identifying analytical snapshot.
    professionals.drop(columns=["professional_id"], errors="ignore").to_csv(
        snapshot_path, index=False, encoding="utf-8"
    )
    result.to_csv(indicators_path, index=False, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source": "DATASUS CNES monthly complete database",
                "archive": archive_path.name,
                "workload_table": workload_member,
                "occupation_dictionary": activity_member,
                "municipalities": 144,
                "professional_categories": categories,
                "counting_rule": "Unique professional per municipality and CBO category",
                "hours_rule": "Sum of ambulatory, other and SUS hospital weekly workload",
                "privacy": "Professional identifiers are removed from the stored analytical snapshot",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "professional_snapshot": snapshot_path,
        "professional_indicators": indicators_path,
        "professional_metadata": metadata_path,
    }
