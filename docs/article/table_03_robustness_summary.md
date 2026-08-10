# Table III. Robustness, agreement, and diagnostic summary

## A. Agreement of alternative configurations with the reference

The reference is `T1 × W1` (equal transport modes, equal availability/proximity
roles, and equal macro-dimension weights). The reference configuration itself
is excluded from the distribution below; therefore, `n = 47` comparisons.

| Metric | Minimum | Median | Maximum |
|---|---:|---:|---:|
| Spearman rank correlation | 0.866 | 0.966 | 0.995 |
| Top-10 overlap | 60.0% | 70.0% | 90.0% |
| Top-quartile overlap | 63.9% | 83.3% | 97.2% |
| Mean absolute rank shift | 3.13 | 7.81 | 17.89 |
| Median absolute rank shift | 2.00 | 5.00 | 19.00 |
| Maximum absolute rank shift | 13 | 36 | 49 |

## B. Municipal stability profiles across all 48 configurations

| Stability profile | Municipalities | Share of 144 |
|---|---:|---:|
| Robust higher capacity-strengthening priority | 26 | 18.1% |
| Scenario-sensitive higher priority | 23 | 16.0% |
| Intermediate or scenario-sensitive | 63 | 43.8% |
| Robust lower relative priority | 32 | 22.2% |
| **Total** | **144** | **100.0%** |

The higher-priority profiles are based on frequency in the top quartile across
the complete scenario space. A frequency of at least 0.75 defines the robust
higher-priority profile; frequencies from 0.25 to below 0.75 define the
scenario-sensitive higher-priority profile. The labels summarize stability
within the 48 predeclared configurations and do not constitute automatic
funding decisions.

## C. Dimension diagnostics

| Dimension pair | Spearman correlation |
|---|---:|
| Institutional deficit vs. service-network deficit | 0.365 |
| Institutional deficit vs. reference transport barrier | 0.022 |
| Service-network deficit vs. reference transport barrier | 0.120 |

The dimension correlations use all 144 municipalities and the `T1` reference
transport scenario. Their low-to-moderate magnitudes indicate that the three
macro-dimensions are not interchangeable empirical measurements. This is a
diagnostic statement, not evidence of causality or statistical independence.

## Reproducibility note

All published scores were reconstructed for `144 × 48 = 6,912`
municipality-configuration combinations. The maximum absolute reconstruction
error was `1.11 × 10⁻¹⁶`. Robustness is claimed only within the tested scenario
space; the analysis does not establish stability under every conceivable
indicator definition or weighting scheme.
