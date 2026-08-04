from __future__ import annotations

from pathlib import Path

import pytest

from empriority.catalog import load_indicator_catalog


def test_load_indicator_catalog(tmp_path: Path) -> None:
    catalog_file = tmp_path / "indicators.yml"
    catalog_file.write_text(
        """
indicators:
  population:
    source: sidra
    description: Population
    dimension: base_municipal
    output: population
    table: 4714
    territorial_level: 6
    territories: all/in/n3/15
    variables: all
    periods: '2022'
""".strip(),
        encoding="utf-8",
    )

    catalog = load_indicator_catalog(catalog_file)
    indicator = catalog.get("population")
    query = indicator.to_query()

    assert catalog.names() == ("population",)
    assert query.table == 4714
    assert query.territorial_level == 6
    assert query.periods == "2022"


def test_unknown_indicator_lists_available_names(tmp_path: Path) -> None:
    catalog_file = tmp_path / "indicators.yml"
    catalog_file.write_text(
        """
indicators:
  population:
    source: sidra
    description: Population
    dimension: base_municipal
    output: population
    table: 4714
    territorial_level: 6
""".strip(),
        encoding="utf-8",
    )

    catalog = load_indicator_catalog(catalog_file)
    with pytest.raises(KeyError, match="population"):
        catalog.get("missing")
