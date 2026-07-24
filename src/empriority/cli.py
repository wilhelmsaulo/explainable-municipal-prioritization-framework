from __future__ import annotations

import typer

from empriority.config import load_settings
from empriority.connectors.sidra import SidraQuery
from empriority.pipeline import build_municipality_reference, collect_sidra_table

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
        help="Classification as ID=CATEGORIES; repeat the option for multiple classifications.",
    ),
    output: str = typer.Option("sidra_table", help="Output base name without extension."),
    config: str = typer.Option("config/project.yml", help="Path to the project configuration."),
) -> None:
    """Collect a table from the official SIDRA API with provenance metadata."""
    classifications: dict[int, str] = {}
    for item in classification or []:
        try:
            identifier, categories = item.split("=", maxsplit=1)
            classifications[int(identifier)] = categories
        except ValueError as exc:
            raise typer.BadParameter(
                "Classifications must use the format ID=CATEGORIES, for example 2=4,5."
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
    frame, data_path, metadata_path = collect_sidra_table(settings, query, output)
    typer.echo(
        f"Collected {len(frame)} SIDRA records. Data: {data_path}. Metadata: {metadata_path}"
    )
    if not frame.empty:
        typer.echo(frame.head().to_string(index=False))


if __name__ == "__main__":
    app()
