# Final scientific-package audit — 2026-08-11

## Scope and decision

This audit reviews the release candidate for the Pará capacity-strengthening
application under `method_version: 1.1.0`. The analytical package passes the
scientific and computational checks below. It must be tagged only after the
provenance corrections identified here are committed and their workflows pass.

The application estimates relative priority for strengthening municipal
service capacity under multimodal access constraints. It does not estimate
violence incidence, hidden incidence, individual risk, or underreporting. No
municipality-specific adjustment, personalized highlighting, or post-result
parameter tuning is permitted.

## Analytical contract

- Territorial universe: all 144 official municipalities of Pará.
- Active non-transport indicators: seven, complete for 144/144 municipalities.
- Institutional indicator: negative observed institutional items divided by
  the number of institutional items actually observed. Missing responses are
  neither deficits nor part of the denominator.
- Transport design: ten selected indicators, five components, three modes,
  twelve predeclared transport scenarios.
- Integrated design: twelve transport scenarios crossed with four
  predeclared macro-weight schemes, totaling 48 configurations.
- Normalization: within-sample percentile rank with average treatment of ties;
  all directions aligned so higher values mean greater strengthening priority.
- Police occurrence and rate variables: preserved in the broad repository but
  absent from the article-specific input matrix and inactive in the framework.
- Population: 2022 Demographic Census released/processed in 2023; retained for
  provenance and legacy fields, not used as a prioritization criterion.

## Source decisions

- Institutional capacity: IBGE MUNIC 2023.
- Health services and professionals: CNES, June 2026 competence.
- Social protection: MDS/SNAS RMA administrative directory.
- Justice: TJPA Balcão Virtual administrative directory.
- Specialized protection network: Ligue 180 panel, manually transcribed and
  curated with an explicit validation trail.
- Roads: MapBiomas infrastructure compilation, reference year 2023. DNIT is
  retained in the source catalog but is not the active road geometry in the
  published construct.
- Ports and passenger crossings: ANTAQ, 2025.
- Navigated waterways: ANTAQ, 2022.
- Aviation: DECEA/ICA, 2026. ANAC is not an active source.
- Municipal calculation boundaries: IBGE 2023 mesh. The simplified IBGE 2022
  mesh is used only for the manuscript/dashboard visualization.

## Verified outputs

| Item | Verification |
|---|---:|
| Article input matrix | 144 rows, 23 columns, 144 unique municipality codes |
| Forbidden police/rate columns in article matrix | 0 |
| Transport scenario matrix | 144 rows, 12 scenario scores |
| Integrated scenario output | 144 rows, 48 scores and 48 ranks |
| Municipal profiles | 144 rows, 144 unique municipality codes |
| Failed input-audit checks | 0 |
| Failed integrated-framework checks | 0 |
| Failed diagnostic/reconstruction checks | 0 |
| Maximum score reconstruction error | 1.11 × 10⁻¹⁶ |

## Release-candidate checksums

These hashes identify the audited analytical files before the release tag.

| File | SHA-256 |
|---|---|
| `config/capacity_priority.yml` | `fd596cbb179e3c0203b27d49f8b0e93d1efc438f3b91026a8d7effff27681bb1` |
| `data/processed/capacity_framework_input_matrix.csv` | `7b330fd92571f0c11fae9da813dfbf731d81d8b5c7a5bf8f5e88daccb0cc5ece` |
| `data/processed/transport/transport_multimodal_scenarios.csv` | `1d25386ec5167395d3b6c65940192a2955d6378189ed848d560df7e0fc290c1f` |
| `data/results/integrated_capacity_priority_profiles.csv` | `6e0ca2f1c456478abb7d43bc08c10b3440f833845419d1758118658c3503b284` |
| `data/results/integrated_capacity_priority_scenarios.csv` | `5cb099723c859b309b6f84aaa8f82c4a82af53b87a5d367427a26ec50adb7c9c` |
| `data/results/integrated_capacity_priority_method.json` | `77f4209d7598dad03ada546eb9e57e8540f9c0b5f09c803b7c2384b633815154` |
| `data/results/integrated_capacity_priority_audit.json` | `d8547f1299ffeeb4409a18381394b320d1a5f3a500fe4470e2c34afa8dae8109` |
| `data/results/capacity_diagnostics_audit.json` | `46cb105111566b3154756aeb65dcdfda4b25eb0c5b83988c13f999ae57bbc494` |

## Provenance finding and correction required before tagging

The generic transport-discovery manifest grouped unrelated MapBiomas links
(aerodromes and dams) under `mapbiomas_other_roads`. Those files were not used
by the road-indicator builder. The builder independently downloaded and used
the correct `outros-trechos.zip`, recorded with SHA-256
`7df6c217fe2ea6bbfd556863fe21a426003042ad774ac7c73bf38e41d58d1585`.

Before tagging, the source catalog and acquisition workflow must register and
validate that checksum explicitly, prioritize `outros-trechos.zip`, and record
the IBGE 2023 municipal-mesh checksum
`0996ffd1b26928dfbd518f67339baa36fd860f50693c1c156f9b4d86fb77c7ad`.
This correction affects provenance metadata only; it does not change the
already audited analytical inputs, scores, ranks, profiles, tables, or figures.

## Freeze gate

The package may be merged and tagged when all of the following are true:

1. the provenance correction above is committed;
2. all required GitHub Actions workflows pass on the resulting head commit;
3. the pull request remains mergeable and is reviewed once more as a whole;
4. the release tag is created from the integrated `main` commit, not from the
   development branch.

## Validation rerun

A documentation-only commit was issued after the automated provenance
manifests advanced the pull-request branch. Its sole purpose is to request the
full release-candidate validation suite from a user-authored commit. It changes
no source data, analytical input, parameter, score, rank, profile, table, or
figure.
