# Methodological core

The framework prioritizes municipalities through a reproducible multicriteria pipeline.

## Analytical sequence

1. Official municipal data are collected through APIs, public repositories or institutional files.
2. Records are standardized using the seven-digit IBGE municipality code.
3. Indicators are organized into analytical dimensions such as violence, institutional capacity, territorial accessibility and socioeconomic vulnerability.
4. Each criterion is transformed to a common 0-1 scale according to its benefit or cost direction.
5. Objective weights are estimated independently with Entropy and CRITIC.
6. The final weight is a convex combination of both vectors, controlled by alpha.
7. Municipalities are ranked with TOPSIS according to their distance from the ideal and anti-ideal solutions.
8. Criterion-level weighted normalized values are exported as local explanatory contributions.
9. Robustness is assessed by repeated small perturbations of the criterion matrix, reporting mean rank, rank dispersion, best and worst ranks, and probability of remaining among the ten highest priorities.

## Hybrid weighting

For criterion j, the final weight is:

`w_j = alpha * w_j_entropy + (1 - alpha) * w_j_critic`

The default value is `alpha = 0.5`, giving equal influence to information diversity and contrast/conflict among criteria. The parameter is declared in `config/criteria.yml` and can be changed for sensitivity scenarios.

## Explainability outputs

The framework exports:

- the final municipal priority score and rank;
- Entropy, CRITIC and hybrid weights for every criterion;
- criterion-level contribution values for every municipality;
- the dominant criterion associated with each municipality;
- rank-stability statistics from perturbation analysis.

These outputs allow the analyst to explain both the global structure of the model and the local reasons why a municipality received a high or low priority.

## Reproducibility

Every external collection produces provenance metadata and optional cache/snapshot files. Analytical runs use explicit configuration files, deterministic random seeds and machine-readable CSV outputs.
