# Explainable Municipal Prioritization Framework

Explainable and reproducible framework for integrating official Brazilian public data sources and supporting municipal-level policy prioritization.

## Current scope

The framework currently provides:

- an authoritative municipality reference collected from the IBGE Localities API;
- standardization and validation of the 144 municipalities of Pará;
- a generic connector for the official SIDRA values API;
- a unified `DataSourceManager` for registering and executing heterogeneous official-source operations;
- a declarative indicator catalog in YAML;
- auditable provenance metadata for every SIDRA collection;
- command-line execution, automated tests and continuous integration.

## Architecture

```text
Official sources -> Connectors -> DataSourceManager -> Validation -> Standardization
                 -> Integration -> Indicators -> Decision model -> Explainability
```

The repository is API-first. Local files are generated only as reproducible outputs, cache or audit snapshots. Source-specific communication remains inside each connector, while pipelines execute named operations through the data-source manager.

Built-in operations currently registered are:

```text
ibge.localities.municipalities
ibge.sidra.values
```

## Requirements

- Python 3.11 or newer

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Municipality reference

```bash
empriority municipalities
```

The command reads `config/project.yml`, queries the official IBGE API, validates the municipal coverage and writes:

```text
data/processed/municipalities.csv
```

## Declarative indicator catalog

Indicators are declared in `config/indicators.yml`. Each entry records its source, analytical dimension, output name and official query parameters.

The initial Base Municipal catalog contains:

- `municipal_population_area_density_2022`;
- `municipal_population_by_sex_2022`.

List the declared indicators:

```bash
empriority indicators
```

Collect one indicator by name:

```bash
empriority collect-indicator municipal_population_by_sex_2022
```

Collect every indicator declared in the catalog:

```bash
empriority collect-all-indicators
```

Each collection produces both data and provenance metadata, for example:

```text
data/processed/municipal_population_by_sex_2022.csv
data/processed/municipal_population_by_sex_2022.metadata.json
```

The population-by-sex query uses SIDRA table 9514, selecting all sex categories while fixing age and age-declaration form at their total categories. This returns total, male and female resident population by municipality without downloading unnecessary age detail.

## Generic SIDRA collection

Direct SIDRA queries remain available for exploration or catalog development:

```bash
empriority sidra \
  --table 4714 \
  --level 6 \
  --territories "all/in/n3/15" \
  --variables all \
  --periods 2022 \
  --output municipal_population_area_density_2022
```

A classification can be supplied more than once using `ID=CATEGORIES`:

```bash
empriority sidra --table 9514 --level 6 -c "2=all" -c "287=100362" -c "286=0"
```

## Tests

```bash
ruff check .
pytest
```

## Development status

This repository is private and under active development. Additional official-source connectors, integration contracts, indicator construction, prioritization models and explainability modules will be added incrementally and reviewed through pull requests.
