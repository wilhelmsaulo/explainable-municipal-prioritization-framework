# Configurable capacity-priority framework

## Purpose

The framework estimates relative municipal priority for strengthening service
capacity under multimodal access constraints. It is a decision-support model,
not an estimator of violence incidence, hidden incidence, causality, individual
risk, or automatic funding entitlement.

The Pará application fixes the universe before analysis as all 144 official
municipalities. No municipality-specific adjustment, personalized selection, or
post-result tuning is permitted.

## Declarative contract

`config/capacity_priority.yml` is the authoritative methodological contract. It
declares:

- the territorial scope and expected number of municipalities;
- input and output paths;
- indicator columns and their directions;
- the hierarchical service-network structure;
- macro-dimension weight scenarios;
- robustness and classification thresholds;
- explicit exclusions and interpretation warnings.

Changing the method requires changing `method_version`. Results must never be
silently recalibrated by editing constants in source code.

## Analytical hierarchy

1. Indicator values are converted to within-sample percentile ranks on `[0, 1]`.
2. Directions are aligned so higher values always mean greater strengthening
   priority.
3. Health, social protection, justice, and specialized protection-network
   indicators are aggregated within components.
4. Components receive equal influence in the service-network dimension,
   preventing components with more source variables from dominating.
5. Institutional deficit, service-network deficit, and multimodal transport
   barrier are combined under every declared macro-weight scenario.
6. Every macro-weight scenario is crossed with every transport scenario.
7. Municipal profiles summarize rank range and frequencies across the complete
   scenario set rather than privileging one ranking.

## Current Pará application

The current configuration combines 12 transport scenarios and four
macro-weight scenarios, generating 48 integrated scenarios for 144
municipalities. Police occurrences and police rates are explicitly excluded
from this application so its target remains capacity strengthening rather than
underreporting.

## Reproducible execution

```bash
empriority run-capacity-framework \
  --config config/capacity_priority.yml
```

The command produces municipal profiles, the full scenario matrix, the
machine-readable method record, and an audit report. GitHub Actions runs the
same command and rejects missing municipalities, invalid weights, missing or
infinite outputs, out-of-range scores, or regression differences introduced
during the initial migration from code constants to configuration.

## Diagnostics and explainability

```bash
empriority diagnose-capacity-framework \
  --config config/capacity_priority.yml
```

This command reads the already published profiles and scenario matrix; it does
not recalculate or replace them. It produces:

- pairwise Spearman correlations among the two capacity-deficit dimensions and
  the transport barrier in the declared reference transport scenario;
- agreement metrics for all 48 scenarios against the declared reference,
  including rank correlation, top-10 overlap, top-quartile overlap, and rank
  shifts;
- a municipality-complete explanation table with mean weighted contributions
  and dominant-dimension frequencies across all scenarios;
- a machine-readable audit that reconstructs every published score and fails
  if any criterion, weight, score, rank, municipality, or scenario is missing or
  inconsistent.

The reference scenario is an interpretive baseline only. It does not receive
extra weight in the municipal profiles, and the diagnostic outputs do not
alter criteria, weights, scores, ranks, or stability classifications.

## Portability

Applying the framework to another territory requires a new versioned YAML
configuration and matrices that follow the declared municipality key and
indicator schema. A new application must define its scope before observing
results and must document any changed indicator, direction, weight, or
threshold. Portability does not authorize transferring Pará-specific empirical
conclusions to another territory.
