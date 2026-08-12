from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


SIDRA_URL = (
    "https://apisidra.ibge.gov.br/values/t/9514/n6/in%20n3%2015/"
    "v/93/p/2022/c2/5?formato=json"
)

def norm_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("ascii")
        .str.upper()
        .str.strip()
    )


def norm_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Z0-9]+", " ", ascii_value.upper()).strip()
    return {"ELDORADO DOS CARAJAS": "ELDORADO DO CARAJAS"}.get(normalized, normalized)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_ibge() -> pd.DataFrame:
    import urllib.request

    with urllib.request.urlopen(SIDRA_URL, timeout=120) as response:
        payload = json.load(response)
    rows = payload[1:]
    result = pd.DataFrame(
        {
            "municipality_code": [str(row["D1C"]) for row in rows],
            "municipality": [row["D1N"].removesuffix(" - PA") for row in rows],
            "female_population_2022": [int(row["V"]) for row in rows],
        }
    )
    result["source_table"] = "SIDRA 9514"
    result["source_year"] = 2022
    return result.sort_values("municipality_code").reset_index(drop=True)


def load_police(files: dict[int, Path]) -> tuple[pd.DataFrame, list[dict[str, object]]]:
    annual = []
    provenance = []
    for expected_year, path in sorted(files.items()):
        filename = path.name
        frame = pd.read_excel(path)
        actual_years = sorted(pd.to_numeric(frame["ANO DO FATO"], errors="raise").unique().tolist())
        if actual_years != [expected_year]:
            raise ValueError(f"{filename}: expected {expected_year}, found {actual_years}")

        municipality = norm_text(frame["MUNICÍPIO(S)"]).replace(
            {"ALTAMIRA/CASTELO DOS SONHOS": "ALTAMIRA"}
        )
        crime = norm_text(frame["CONSOLIDADO(S)"])
        specification = norm_text(frame["ESPECIFICAÇÃO CRIME"])
        victim_sex = norm_text(frame["SEXO VÍTIMA"])
        female = victim_sex.eq("F")

        local = pd.DataFrame({"municipality": municipality, "year": expected_year})
        local = local.loc[female].copy()
        fc = crime.loc[female]
        fs = specification.loc[female]
        local["all_female_records"] = 1
        local["lesao_corporal"] = fc.eq("LESAO CORPORAL").astype(int)
        local["violencia_domestica_lesao"] = (
            fc.eq("LESAO CORPORAL") & fs.str.contains("VIOLENCIA DOMESTICA", regex=False)
        ).astype(int)
        local["estupro"] = fc.eq("ESTUPRO").astype(int)
        local["estupro_vulneravel"] = fc.eq("ESTUPRO DE VULNERAVEL").astype(int)
        local["violencia_sexual"] = fc.isin(["ESTUPRO", "ESTUPRO DE VULNERAVEL"]).astype(int)
        local["homicidio_mulher"] = fc.eq("HOMICIDIO").astype(int)
        attempt = fs.str.contains("TENTATIVA DE FEMINICIDIO", regex=False)
        direct_or_specified = fc.eq("FEMINICIDIO") | (
            fc.eq("HOMICIDIO") & fs.str.contains("FEMINICIDIO", regex=False)
        )
        local["feminicidio"] = (direct_or_specified & ~attempt).astype(int)
        local["tentativa_feminicidio"] = attempt.astype(int)
        local["selected_vaw_records"] = (
            local["violencia_domestica_lesao"]
            + local["violencia_sexual"]
            + local["feminicidio"]
            + local["tentativa_feminicidio"]
        )
        count_cols = [column for column in local.columns if column not in {"municipality", "year"}]
        annual.append(local.groupby(["municipality", "year"], as_index=False)[count_cols].sum())
        provenance.append(
            {
                "year": expected_year,
                "original_filename": filename,
                "sha256": sha256(path),
                "rows": int(len(frame)),
                "female_rows": int(female.sum()),
                "exact_duplicate_rows_retained": int(frame.duplicated().sum()),
                "municipality_labels_before_alias": int(municipality.loc[female].nunique() + 1),
                "municipalities_after_alias": int(municipality.loc[female].nunique()),
            }
        )
    return pd.concat(annual, ignore_index=True).sort_values(["year", "municipality"]), provenance


def main() -> None:
    parser = argparse.ArgumentParser(description="Build contextual VAW population and police tables.")
    for year in range(2022, 2026):
        parser.add_argument(f"--police-{year}", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/contextual"))
    args = parser.parse_args()
    files = {year: getattr(args, f"police_{year}") for year in range(2022, 2026)}
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    population = load_ibge()
    police, provenance = load_police(files)
    population["municipality_key"] = population["municipality"].map(norm_name)
    police["municipality_key"] = police["municipality"].map(norm_name)
    code_map = population[["municipality_code", "municipality", "municipality_key", "female_population_2022"]]
    contextual = police.merge(code_map, on="municipality_key", how="left", validate="many_to_one", suffixes=("_police", ""))
    if contextual["municipality_code"].isna().any():
        raise ValueError(contextual.loc[contextual["municipality_code"].isna(), "municipality_police"].unique())
    count_cols = [
        "all_female_records", "violencia_domestica_lesao", "lesao_corporal", "violencia_sexual",
        "estupro", "estupro_vulneravel", "homicidio_mulher", "feminicidio",
        "tentativa_feminicidio", "selected_vaw_records",
    ]
    for column in count_cols:
        contextual[f"rate_{column}_per_100k_women"] = contextual[column] / contextual["female_population_2022"] * 100000
    ordered = ["municipality_code", "municipality", "year", "female_population_2022", *count_cols]
    ordered += [column for column in contextual.columns if column.startswith("rate_")]
    contextual = contextual[ordered].sort_values(["year", "municipality_code"])
    population.drop(columns="municipality_key").to_csv(out / "ibge_female_population_2022_pa.csv", index=False)
    police.drop(columns="municipality_key").to_csv(out / "police_municipal_year_2022_2025_pa.csv", index=False)
    contextual.to_csv(out / "contextual_vaw_municipal_year_2022_2025_pa.csv", index=False)
    audit = {
        "schema_version": "1.1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ibge": {
            "source": SIDRA_URL,
            "table": 9514,
            "variable": 93,
            "sex_classification": 5,
            "year": 2022,
            "municipalities": int(len(population)),
            "sum_female_population": int(population["female_population_2022"].sum()),
        },
        "police": {
            "reference_period": "2022-2025",
            "annual_rows": int(len(police)),
            "municipalities_per_year": police.groupby("year")["municipality"].nunique().to_dict(),
            "raw_files": provenance,
            "duplicates_rule": "Exact duplicate rows are retained because the source has no unique occurrence identifier; equality across all exported fields is not sufficient evidence of duplicate events.",
            "selected_vaw_definition": "Female-victim records classified as domestic-violence bodily injury, rape, rape of a vulnerable person, feminicide, or explicit attempted feminicide.",
        },
        "contextual_table": {
            "rows": int(len(contextual)),
            "municipalities": int(contextual["municipality_code"].nunique()),
            "years": sorted(contextual["year"].unique().tolist()),
            "missing_female_population": int(contextual["female_population_2022"].isna().sum()),
        },
        "primary_model_changed": False,
    }
    (out / "contextual_vaw_data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
