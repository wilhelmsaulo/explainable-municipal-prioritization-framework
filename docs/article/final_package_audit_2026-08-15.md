# Final article-package audit, 2026-08-15

## Scope

This audit verifies the repository state intended to accompany the article
under `method_version: 1.2.0`. It covers the declared configuration, published
diagnostic outputs, article-figure generation, and the cartographic additions
to the statewide top-quartile-frequency map.

## Analytical consistency

- Territorial coverage: 144 unique municipalities.
- Transport design: 12 scenarios.
- Macro-weight design: four schemes.
- Primary additive design: 48 integrated configurations.
- Maximum score-reconstruction error: `2.220446049250313e-16`.
- All diagnostic values are complete and finite.
- The published diagnostic files were reconstructed without a change in their
  SHA-256 hashes.

## Spatial diagnostic

- Variable: `top_quartile_frequency`.
- Spatial weights: first-order queen contiguity, row-standardized.
- Municipalities: 144.
- Undirected neighbor links: 384.
- Neighbor range: 2 to 12; no spatial islands.
- Moran's I: `0.005900235912784742`.
- Permutation test: 999 permutations, seed 42, one-sided pseudo-p value 0.42.
- Interpretation: no statistically significant positive global spatial
  autocorrelation at alpha 0.05.

## Article figures

- Figure 1 was replaced by the approved five-phase methodological flow in
  editable SVG format.
- The statewide map was regenerated from the frozen municipal profile output.
- The revised map adds a four-point compass rose, an approximate 0--300 km
  local scale bar, and a Brazil locator inset highlighting Pará.
- The locator geometry has no analytical role and has a separate provenance
  record under `data/geospatial/`.
- Two consecutive executions of `python scripts/build_article_figures.py`
  produced identical SHA-256 hashes for the revised map's PNG and SVG files.

## Local execution

Python byte-code compilation, direct reconstruction of the capacity
diagnostics, and article-figure regeneration completed successfully. The full
development suite (`ruff` and `pytest`) requires the optional `dev`
dependencies and is delegated to the repository's GitHub Actions `tests`
workflow. A final tag must be created only after the pull-request checks pass
and the update is merged into `main`.
