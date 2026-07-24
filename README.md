# Explainable Municipal Prioritization Framework

Explainable and reproducible framework for integrating official Brazilian public data sources and supporting municipal-level policy prioritization.

## Current scope

The first implementation builds the authoritative municipality reference table directly from the IBGE Localities API, standardizes municipality identifiers and validates the expected 144 municipalities of Pará.

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

## First execution

```bash
empriority municipalities
```

The command reads `config/project.yml`, queries the official IBGE API, validates the municipal coverage and writes:

```text
data/processed/municipalities.csv
```

## Tests

```bash
ruff check .
pytest
```

## Development status

This repository is private and under active development. Data-source connectors, indicator construction, prioritization models and explainability modules will be added incrementally and reviewed through pull requests.
