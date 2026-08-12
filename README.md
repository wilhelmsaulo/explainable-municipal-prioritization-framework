# Explainable Municipal Prioritization Framework

Multicriteria model for municipal prioritization of response capacity to violence against women in Pará, Brazil.

## Current article application

The active Pará application prioritizes the strengthening of municipal and
intersectoral response capacity to violence against women. It covers all 144
municipalities and jointly considers institutional deficits, service-network
availability, and multimodal accessibility constraints. The analysis crosses
12 accessibility scenarios with four declared macro-weight schemes, producing
48 integrated configurations.

The application uses institutional capacity (MUNIC 2023), health services and
professionals (CNES), specialized social assistance (MDS/SNAS), state judicial
access (TJPA), the validated protection network (Ligue 180), and multimodal
transport sources (MapBiomas, ANTAQ, and DECEA/ICA). The population field
currently named `population_2023` represents the 2022 Demographic Census
released/processed in 2023.

Police data for 2022--2025 are preserved for contextual and sensitivity
analyses but are not criteria in the primary score. Female population from the
2022 Demographic Census supports contextual analyses and denominators where
applicable. The model does not estimate violence incidence, hidden incidence,
individual risk, or underreporting.

See `docs/capacity_priority_framework.md` for the authoritative analytical
contract and reproducible commands.

## Repository capabilities and legacy components

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

This repository is private and under active development. The capacity-priority
application is isolated through a versioned declarative configuration, audited
input matrix, complete 48-scenario outputs, and reproducibility workflows.
Generic police-import and TOPSIS components remain available as legacy,
reusable repository capabilities but are not part of the active article
application.

## Interactive scientific dashboard

**Live experimental dashboard:** https://explainable-municipal-prioritization-framework-zyur6g28v6z5uba.streamlit.app/


A read-only Streamlit dashboard presents the 144 municipalities and all 48
precomputed configurations without recalculating scores or permitting arbitrary
parameter changes. It includes the statewide view, municipal profiles,
municipality comparison, stability diagnostics, and CSV export.

```bash
python -m pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

See `dashboard/README.md` for the dashboard-specific data contract.
