from __future__ import annotations

import typer

from empriority.analysis import run_prioritization
from empriority.catalog import load_indicator_catalog
from empriority.config import load_settings
from empriority.connectors.sidra import SidraQuery
from empriority.integrated_priority import build_integrated_priority_profiles
from empriority.integration import build_integrated_matrix
from empriority.pipeline import (
    build_municipality_reference,
    collect_catalog_indicator,
    collect_munic,
    collect_project,
    collect_sidra_table,
)

app = typer.Typer(no_args_is_help=True)


@app.command("municipalities")
def municipalities(
    config: str = typer.Option("config/project.yml", help="Path to the project configuration."),
) -> None:
    """Collect and validate the municipal reference table."""
    settings = load_settings(config)
    frame, validation, output_path = build_municipality_reference(settings)
    typer.echo(
        f"Validated {validation.observed_count} municipalities for "
        f"{settings.project.state_code}. Output: {output_path}"
    )
    typer.echo(frame.head().to_string(index=False))


@app.command("munic")
def munic(
    year: int = typer.Option(2023, min=2000, max=2100, help="MUNIC reference year."),
    config: str = typer.Option("config/project.yml", help="Path to project configuration."),
) -> None:
    """Download the official MUNIC workbook and create its worksheet inventory."""
    settings = load_settings(config)
    outputs = collect_munic(settings, year=year)
    for name, path in outputs.items():
        typer.echo(f"OK {name}: {path}")


@app.command("sidra")
def sidra(
    table: int = typer.Option(..., help="SIDRA table number."),
    level: int = typer.Option(..., help="SIDRA territorial level, for example 6 for municipality."),
    territories: str = typer.Option("all", help="Territory selection accepted by SIDRA."),
    variables: str = typer.Option("all", help="Variable selection accepted by SIDRA."),
    periods: str = typer.Option("last", help="Period selection accepted by SIDRA."),
    classification: list[str] | None = typer.Option(
        None,
        "--classification",
        "-c",
        help="Classification as ID=CATEGORIES; repeat for multiple classifications.",
    ),
    output: str = typer.Option("sidra_table", help="Output base name without extension."),
    config: str = typer.Option("config/project.yml", help="Path to project configuration."),
    refresh: bool = typer.Option(False, help="Ignore cache and request the official source again."),
) -> None:
    """Collect a table from the official SIDRA API with provenance metadata."""
    classifications: dict[int, str] = {}
    for item in classification or []:
        try:
            identifier, categories = item.split("=", maxsplit=1)
            classifications[int(identifier)] = categories
        except ValueError as exc:
            raise typer.BadParameter(
                "Classifications must use ID=CATEGORIES, for example 2=4,5."
            ) from exc

    settings = load_settings(config)
    query = SidraQuery(
        table=table,
        territorial_level=level,
        territories=territories,
        variables=variables,
        periods=periods,
        classifications=classifications,
    )
    frame, data_path, metadata_path = collect_sidra_table(
        settings, query, output, refresh=refresh
    )
    typer.echo(
        f"Collected {len(frame)} SIDRA records. Data: {data_path}. Metadata: {metadata_path}"
    )
    if not frame.empty:
        typer.echo(frame.head().to_string(index=False))


@app.command("indicators")
def indicators(
    catalog: str = typer.Option(
        "config/indicators.yml", help="Path to the declarative indicator catalog."
    ),
) -> None:
    """List indicators currently declared in the project catalog."""
    loaded = load_indicator_catalog(catalog)
    for name in loaded.names():
        item = loaded.get(name)
        typer.echo(f"{name}\t{item.dimension}\t{item.description}")


@app.command("collect-indicator")
def collect_indicator(
    name: str = typer.Argument(..., help="Indicator name declared in the catalog."),
    catalog: str = typer.Option(
        "config/indicators.yml", help="Path to the declarative indicator catalog."
    ),
    config: str = typer.Option("config/project.yml", help="Path to project configuration."),
    refresh: bool = typer.Option(False, help="Ignore cache and request the official source again."),
) -> None:
    """Collect one named indicator from its official source."""
    settings = load_settings(config)
    try:
        frame, data_path, metadata_path = collect_catalog_indicator(
            settings, name, catalog, refresh=refresh
        )
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"Collected indicator '{name}' with {len(frame)} records. "
        f"Data: {data_path}. Metadata: {metadata_path}"
    )


@app.command("collect-all-indicators")
def collect_all_indicators(
    catalog: str = typer.Option(
        "config/indicators.yml", help="Path to the declarative indicator catalog."
    ),
    config: str = typer.Option("config/project.yml", help="Path to project configuration."),
    refresh: bool = typer.Option(False, help="Ignore cache and request every source again."),
) -> None:
    """Collect every indicator declared in the catalog."""
    settings = load_settings(config)
    loaded = load_indicator_catalog(catalog)
    completed = 0
    failures: list[str] = []

    for name in loaded.names():
        try:
            frame, data_path, metadata_path = collect_catalog_indicator(
                settings, name, catalog, refresh=refresh
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: {exc}")
            typer.echo(f"FAILED {name}: {exc}", err=True)
            continue

        completed += 1
        typer.echo(
            f"OK {name}: {len(frame)} records. Data: {data_path}. Metadata: {metadata_path}"
        )

    typer.echo(f"Completed {completed} of {len(loaded.names())} indicators.")
    if failures:
        raise typer.Exit(code=1)


@app.command("collect")
def collect(
    catalog: str = typer.Option(
        "config/indicators.yml", help="Path to the declarative indicator catalog."
    ),
    config: str = typer.Option("config/project.yml", help="Path to project configuration."),
    police_file: str | None = typer.Option(
        None,
        help="Optional public police CSV/XLSX file covering the 2022-2025 period.",
    ),
    refresh: bool = typer.Option(False, help="Ignore cache and request official APIs again."),
) -> None:
    """Run the current end-to-end data collection pipeline."""
    settings = load_settings(config)
    outputs = collect_project(
        settings,
        catalog_path=catalog,
        police_path=police_file,
        refresh=refresh,
    )
    for name, path in outputs.items():
        typer.echo(f"OK {name}: {path}")


@app.command("build-matrix")
def build_matrix(
    municipalities: str = typer.Option(
        "data/processed/municipalities.csv", help="Municipality reference CSV."
    ),
    indicator: list[str] | None = typer.Option(
        None,
        "--indicator",
        "-i",
        help="Indicator as NAME=CSV_PATH; repeat for multiple indicators.",
    ),
    police: str | None = typer.Option(None, help="Optional normalized police CSV."),
    output: str = typer.Option(
        "data/processed/integrated_municipal_matrix.csv", help="Integrated matrix path."
    ),
) -> None:
    """Build one-row-per-municipality analytical matrix from collected outputs."""
    indicator_paths: dict[str, str] = {}
    for item in indicator or []:
        try:
            name, path = item.split("=", maxsplit=1)
        except ValueError as exc:
            raise typer.BadParameter("Indicators must use NAME=CSV_PATH.") from exc
        indicator_paths[name] = path
    path = build_integrated_matrix(
        municipalities,
        indicator_paths,
        police_path=police,
        output_path=output,
    )
    typer.echo(f"OK integrated_matrix: {path}")


@app.command("prioritize")
def prioritize(
    data: str = typer.Option(..., help="Integrated municipal CSV containing the criteria."),
    criteria: str = typer.Option(
        "config/criteria.yml", help="Path to multicriteria configuration."
    ),
    output: str = typer.Option("data/results", help="Directory for analytical results."),
    iterations: int = typer.Option(200, min=1, help="Sensitivity-analysis iterations."),
    seed: int = typer.Option(42, help="Random seed for reproducibility."),
) -> None:
    """Run hybrid entropy-CRITIC weighting, TOPSIS and sensitivity analysis."""
    paths = run_prioritization(
        data,
        criteria_path=criteria,
        output_directory=output,
        sensitivity_iterations=iterations,
        seed=seed,
    )
    for name, path in paths.items():
        typer.echo(f"OK {name}: {path}")


@app.command("run-capacity-framework")
def run_capacity_framework(
    config: str = typer.Option(
        "config/capacity_priority.yml",
        help="Path to the declarative capacity-priority framework configuration.",
    ),
) -> None:
    """Run the configured hierarchical capacity-priority framework."""
    paths = build_integrated_priority_profiles(config_path=config)
    for name, path in paths.items():
        typer.echo(f"OK {name}: {path}")


if __name__ == "__main__":
    app()
