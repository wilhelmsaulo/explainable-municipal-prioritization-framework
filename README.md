# Explainable Municipal Prioritization Framework

Explainable and reproducible framework for integrating official Brazilian public data sources and supporting municipal-level policy prioritization.

## Current scope

The framework currently provides:

- an authoritative municipality reference collected from the IBGE Localities API;
- standardization and validation of the 144 municipalities of Pará;
- a generic connector for the official SIDRA values API;
- auditable provenance metadata for every SIDRA collection;
- command-line execution, automated tests and continuous integration.

## Architecture

```text
Official sources -> Connectors -> Validation -> Standardization -> Integration
                 -> Indicators -> Decision model -> Explainability -> Results
```

The repository is API-first. Local files are generated only as reproducible outputs, cache or audit snapshots.

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

## Generic SIDRA collection

The SIDRA command follows the official API path structure and accepts table, territorial level, territories, variables, periods and optional classifications.

```bash
empriority sidra \
  --table 4709 \
  --level 6 \
  --territories "all/in/n3/15" \
  --variables 93 \
  --periods 2022 \
  --output population_2022
```

A classification can be supplied more than once using `ID=CATEGORIES`:

```bash
empriority sidra --table 202 --level 6 -c "2=4,5" -c "1=all"
```

Each collection produces both the data and an audit sidecar:

```text
data/processed/population_2022.csv
data/processed/population_2022.metadata.json
```

The metadata records the official endpoint, query parameters, UTC collection time, number of records and the mapping of normalized columns to the labels returned by SIDRA.

## Tests

```bash
ruff check .
pytest
```

## Development status

This repository is private and under active development. Additional official-source connectors, integration contracts, indicator construction, prioritization models and explainability modules will be added incrementally and reviewed through pull requests.
