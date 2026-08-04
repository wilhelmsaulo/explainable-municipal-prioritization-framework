# Explainable Municipal Prioritization Framework

Explainable and reproducible framework for integrating official Brazilian public data sources and supporting municipal-level policy prioritization.

## Current scope

The framework currently provides:

- an authoritative municipality reference collected from the IBGE Localities API;
- standardization and validation of the 144 municipalities of Pará;
- a generic connector for the official SIDRA values API;
- a unified `DataSourceManager`;
- declarative indicator and criteria catalogs in YAML;
- cache, snapshots and provenance metadata;
- police-data import from CSV/XLSX;
- hybrid Entropy-CRITIC weighting;
- TOPSIS municipal prioritization;
- criterion-level local explanations;
- perturbation-based rank sensitivity analysis;
- command-line execution, automated tests and continuous integration.

## Architecture

```text
Official sources -> Connectors -> DataSourceManager -> Validation -> Standardization
                 -> Integration -> Indicators -> Hybrid MCDA -> Explainability
                 -> Sensitivity -> Results
```

The repository is API-first. Local files are generated only as reproducible outputs, cache or audit snapshots.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

## Data collection

Run the current collection pipeline:

```bash
empriority collect
```

Include a public police file when available:

```bash
empriority collect --police-file path/to/police_2022_2025.xlsx
```

Ignore cache and refresh official sources:

```bash
empriority collect --refresh
```

## Declarative indicators

Indicators are declared in `config/indicators.yml`. The initial municipal catalog includes population, area, density and population by sex.

```bash
empriority indicators
empriority collect-all-indicators
```

## Municipal prioritization

Copy `config/criteria.example.yml` to `config/criteria.yml`, replace the example columns with the final integrated indicators and run:

```bash
empriority prioritize \
  --data data/processed/integrated_municipal_matrix.csv \
  --criteria config/criteria.yml \
  --iterations 500
```

The analytical command exports:

```text
data/results/municipal_priority_ranking.csv
data/results/criterion_weights.csv
data/results/municipal_contributions.csv
data/results/rank_sensitivity.csv
```

The methodological core is documented in `docs/methodology.md`.

## Direct SIDRA collection

Direct SIDRA queries remain available for exploration and catalog development:

```bash
empriority sidra \
  --table 4714 \
  --level 6 \
  --territories "all/in/n3/15" \
  --variables all \
  --periods 2022 \
  --output municipal_population_area_density_2022
```

## Tests

```bash
ruff check .
pytest
```

## Development status

This repository is private and under active development. The implemented core is sufficient to collect initial official data, receive the police dataset, execute the hybrid multicriteria model and generate explainable and sensitivity-aware municipal rankings. Additional thematic connectors and final indicator definitions will be added as the study dataset is consolidated.
