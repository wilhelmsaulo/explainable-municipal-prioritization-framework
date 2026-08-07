from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

SOURCE_PATH = Path("data/source/protection_network_ligue180_pa_transcribed.csv")
VALID_STATUSES = {
    "completo",
    "sigiloso",
    "sem contato visivel",
    "sem endereco",
}
MUNICIPALITY_ALIASES = {
    "icoaraci": "belem",
}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _present_public(value: object) -> int:
    normalized = _norm(value)
    return int(bool(normalized) and normalized not in {"n i", "sigiloso"})


def _is_confidential(value: object) -> int:
    return int(_norm(value) == "sigiloso")


def _category_flags(category: object) -> dict[str, int]:
    value = _norm(category)
    return {
        "protection_network_specialized_police": int("delegacia" in value),
        "protection_network_specialized_judiciary": int("juizado" in value or "vara" in value),
        "protection_network_specialized_prosecution": int("promotoria" in value),
        "protection_network_specialized_defense": int("defensoria" in value),
        "protection_network_shelter": int("abrigo" in value or "acolhimento" in value),
        "protection_network_reference_center": int(
            "centro de referencia" in value
            or "casa da mulher brasileira" in value
            or "nucleo especializado" in value
            or "sala lilas" in value
        ),
        "protection_network_health_service": int("servico de saude" in value),
        "protection_network_maria_da_penha_patrol": int("patrulha maria da penha" in value),
        "protection_network_women_policy_body": int(
            "politica para mulheres" in value or "coordenadoria" in value
        ),
    }


def build_protection_network_indicators(
    source_path: str | Path = SOURCE_PATH,
    matrix_path: str | Path = "data/processed/integrated_municipal_matrix.csv",
    output_directory: str | Path = "data/processed",
) -> dict[str, Path]:
    source_path = Path(source_path)
    matrix_path = Path(matrix_path)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    source = pd.read_csv(source_path, dtype=str).fillna("")
    matrix = pd.read_csv(matrix_path, dtype={"municipality_code": str})
    reference = matrix[["municipality_code", "municipality"]].drop_duplicates().copy()
    reference["municipality_key"] = reference["municipality"].map(_norm)
    key_to_code = dict(zip(reference["municipality_key"], reference["municipality_code"]))
    key_to_name = dict(zip(reference["municipality_key"], reference["municipality"]))

    source["municipality_raw"] = source["Município"]
    source["municipality_key"] = source["Município"].map(_norm).replace(MUNICIPALITY_ALIASES)
    source["municipality_code"] = source["municipality_key"].map(key_to_code)
    source["municipality"] = source["municipality_key"].map(key_to_name)
    source["transcription_status_key"] = source["Situação da Transcrição"].map(_norm)
    source["protection_network_record_validated"] = (
        source["transcription_status_key"].isin(VALID_STATUSES).astype(int)
    )
    source["protection_network_public_address"] = source["Endereço do Serviço"].map(_present_public)
    source["protection_network_public_phone"] = source["Telefone"].map(_present_public)
    source["protection_network_confidential_address"] = source["Endereço do Serviço"].map(
        _is_confidential
    )
    source["category_key"] = source["Categoria Padronizada"].map(_norm)

    flags = source["Categoria Padronizada"].map(_category_flags).apply(pd.Series)
    source = pd.concat([source, flags], axis=1)

    unmatched = source[source["municipality_code"].isna()].copy()
    matched = source[source["municipality_code"].notna()].copy()
    if matched.empty:
        raise RuntimeError("No protection-network records matched the municipal reference")

    matched["protection_network_record_transcribed"] = 1
    matched["validated_category_key"] = matched["category_key"].where(
        matched["protection_network_record_validated"].eq(1), ""
    )

    count_columns = [
        "protection_network_record_transcribed",
        "protection_network_record_validated",
        "protection_network_public_address",
        "protection_network_public_phone",
        "protection_network_confidential_address",
        "protection_network_specialized_police",
        "protection_network_specialized_judiciary",
        "protection_network_specialized_prosecution",
        "protection_network_specialized_defense",
        "protection_network_shelter",
        "protection_network_reference_center",
        "protection_network_health_service",
        "protection_network_maria_da_penha_patrol",
        "protection_network_women_policy_body",
    ]

    for column in count_columns[5:]:
        matched[column] = matched[column] * matched["protection_network_record_validated"]

    summary = matched.groupby(["municipality_code", "municipality"], as_index=False).agg(
        **{column: (column, "sum") for column in count_columns},
        protection_network_validated_category_diversity=(
            "validated_category_key",
            lambda series: int(series[series.ne("")].nunique()),
        ),
    )
    summary["protection_network_uncertain_records"] = (
        summary["protection_network_record_transcribed"]
        - summary["protection_network_record_validated"]
    )
    summary["protection_network_covered"] = (
        summary["protection_network_record_validated"].gt(0).astype(int)
    )
    summary["protection_network_access_deficit"] = (
        summary["protection_network_covered"].eq(0).astype(int)
    )
    summary["protection_network_specialized_non_health_services"] = summary[
        [
            "protection_network_specialized_police",
            "protection_network_specialized_judiciary",
            "protection_network_specialized_prosecution",
            "protection_network_specialized_defense",
            "protection_network_shelter",
            "protection_network_reference_center",
            "protection_network_maria_da_penha_patrol",
            "protection_network_women_policy_body",
        ]
    ].sum(axis=1)

    result = reference.drop(columns="municipality_key").merge(
        summary,
        on=["municipality_code", "municipality"],
        how="left",
    )
    indicator_columns = [
        column for column in result.columns if column.startswith("protection_network_")
    ]
    for column in indicator_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0)

    population = pd.to_numeric(
        matrix[["municipality_code", "population_2023"]].drop_duplicates()["population_2023"],
        errors="coerce",
    )
    population_map = dict(
        zip(
            matrix[["municipality_code", "population_2023"]].drop_duplicates()["municipality_code"],
            population,
        )
    )
    result["_population"] = result["municipality_code"].map(population_map)
    for column in [
        "protection_network_record_validated",
        "protection_network_specialized_non_health_services",
        "protection_network_specialized_police",
        "protection_network_shelter",
        "protection_network_reference_center",
    ]:
        result[f"{column}_per_100k_population"] = result[column] / result["_population"] * 100_000
    result = result.drop(columns="_population")

    if len(result) != 144 or result["municipality_code"].nunique() != 144:
        raise AssertionError("Protection-network result must contain exactly 144 municipalities")
    if int(result["protection_network_record_validated"].sum()) <= 0:
        raise AssertionError("Validated protection-network total is zero")

    indicators_path = output / "protection_network_indicators_pa.csv"
    normalized_path = output / "protection_network_records_normalized_pa.csv"
    unmatched_path = output / "protection_network_unmatched_records_pa.csv"
    metadata_path = output / "protection_network_indicators_pa.metadata.json"

    result.to_csv(indicators_path, index=False, encoding="utf-8")
    matched.to_csv(normalized_path, index=False, encoding="utf-8")
    unmatched.to_csv(unmatched_path, index=False, encoding="utf-8")
    metadata_path.write_text(
        json.dumps(
            {
                "source": "Painel da Rede de Atendimento à Mulher - Ligue 180 / Ministério das Mulheres",
                "source_file": str(source_path),
                "raw_records": int(len(source)),
                "matched_records": int(len(matched)),
                "unmatched_records": int(len(unmatched)),
                "validated_records": int(matched["protection_network_record_validated"].sum()),
                "municipalities_with_validated_services": int(
                    result["protection_network_covered"].sum()
                ),
                "public_addresses": int(matched["protection_network_public_address"].sum()),
                "confidential_addresses": int(
                    matched["protection_network_confidential_address"].sum()
                ),
                "method": "Manual official-panel transcription retained in full; primary indicators exclude explicitly uncertain, non-individualized or unidentified records. Icoaraci is standardized to Belém.",
                "confidentiality": "SIGILOSO values are retained as labels and excluded from public-address/geocoding fields.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "indicators": indicators_path,
        "normalized_records": normalized_path,
        "unmatched_records": unmatched_path,
        "metadata": metadata_path,
    }
