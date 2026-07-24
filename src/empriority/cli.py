from __future__ import annotations

import typer

from empriority.config import load_settings
from empriority.pipeline import build_municipality_reference

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


if __name__ == "__main__":
    app()
