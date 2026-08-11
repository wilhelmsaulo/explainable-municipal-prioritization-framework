# Multimethod and stochastic-weight validation (method 1.2.0)

## Scientific scope

The research target remains **“Relative priority for strengthening municipal service
capacity under multimodal access constraints.”** The audited hierarchical additive model
remains the primary method. Its 144 Pará municipalities, seven active non-transport
indicators, direction-aligned within-sample percentile ranks, equal-component service
hierarchy, 12 transport scenarios, and four predeclared macro-weight schemes are unchanged.

Police records and rates, population, hidden-incidence or underreporting estimates,
individual risk, and violence incidence are not active criteria. Validation neither tunes
results nor introduces municipality-specific adjustments, clustering, supervised learning,
neural networks, or generated rankings.

## Independent deterministic methods

Each of the 48 transport-scenario and macro-weight combinations uses the same aligned
three-column matrix: institutional deficit, service-network deficit, and multimodal
transport barrier. All columns are benefit criteria.

* **Additive (primary):** the audited weighted sum is reproduced without alteration.
* **TOPSIS:** vector normalization, weighted positive and negative ideals, Euclidean
  separation, and relative closeness.
* **PROMETHEE II:** the parameter-free usual preference function. Strict superiority is
  preference and equality is indifference; no thresholds are introduced. Positive,
  negative, and net flows are reported, with the net flow linearly normalized to `[0, 1]`.

The cross-product contains 144 method-scenario configurations and 20,736 municipal
score/rank records. Pairwise method comparisons report Spearman correlation, top-10 and
top-quartile overlap, and mean and maximum absolute rank shift. At a tied cutoff, fractional
membership is allocated equally so top-set mass is exactly 10 or 36.

## SMAA-inspired analysis

For the additive model, 10,000 macro-weight vectors are drawn with seed 42. Dirichlet
`(1,1,1)` barycentric coefficients sample uniformly over the triangle whose vertices are
the institutional, service-network, and transport emphasis vectors. Thus weights sum to one
and each component remains in `[0.25, 0.50]`. Every draw is evaluated under all 12 transport
scenarios with equal frequency: 120,000 evaluations per municipality.

Outputs include mean and standard deviation of rank, rank-1, top-10 and top-quartile
acceptability, and the complete rank 1–144 distribution. The analysis describes robustness
to predeclared uncertainties; it does not replace the primary results.

## Reproduction

```bash
empriority run-capacity-framework --config config/capacity_priority.yml
empriority diagnose-capacity-framework --config config/capacity_priority.yml
empriority validate-capacity-multimethod --config config/capacity_priority.yml
```

The machine-readable audit checks territorial, scenario, method and record coverage,
weight constraints, finite scores/ranks, complete acceptability mass, inactive excluded
variables, and additive reconstruction with maximum absolute error at most `1e-12`.
