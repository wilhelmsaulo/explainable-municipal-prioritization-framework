# Table II. Predeclared transport and macro-weight scenarios

## A. Multimodal transport scenarios

| ID | Modal structure (road, water, air) | Role structure (availability, proximity) |
|---|---:|---:|
| T1 — Equal modes; equal roles | (1/3, 1/3, 1/3) | (1/2, 1/2) |
| T2 — Equal modes; availability emphasis | (1/3, 1/3, 1/3) | (2/3, 1/3) |
| T3 — Equal modes; proximity emphasis | (1/3, 1/3, 1/3) | (1/3, 2/3) |
| T4 — Road emphasis; equal roles | (1/2, 1/4, 1/4) | (1/2, 1/2) |
| T5 — Road emphasis; availability emphasis | (1/2, 1/4, 1/4) | (2/3, 1/3) |
| T6 — Road emphasis; proximity emphasis | (1/2, 1/4, 1/4) | (1/3, 2/3) |
| T7 — Waterway emphasis; equal roles | (1/4, 1/2, 1/4) | (1/2, 1/2) |
| T8 — Waterway emphasis; availability emphasis | (1/4, 1/2, 1/4) | (2/3, 1/3) |
| T9 — Waterway emphasis; proximity emphasis | (1/4, 1/2, 1/4) | (1/3, 2/3) |
| T10 — Air emphasis; equal roles | (1/4, 1/4, 1/2) | (1/2, 1/2) |
| T11 — Air emphasis; availability emphasis | (1/4, 1/4, 1/2) | (2/3, 1/3) |
| T12 — Air emphasis; proximity emphasis | (1/4, 1/4, 1/2) | (1/3, 2/3) |

## B. Macro-dimension weight scenarios

| ID | Institutional deficit | Service-network deficit | Transport barrier |
|---|---:|---:|---:|
| W1 — Equal dimensions | 1/3 | 1/3 | 1/3 |
| W2 — Institutional emphasis | 1/2 | 1/4 | 1/4 |
| W3 — Service-network emphasis | 1/4 | 1/2 | 1/4 |
| W4 — Transport emphasis | 1/4 | 1/4 | 1/2 |

Each transport scenario is crossed with every macro-weight scenario. The full
design therefore contains `12 × 4 = 48` integrated configurations. Each
municipality is evaluated in all 48 configurations, and no configuration
receives greater frequency weight. `T1 × W1` is retained only as a transparent
interpretive baseline; it is not treated as ground truth and has no privileged
role in the robustness profiles.

Within water transport, port, passenger-crossing, and navigated-waterway
components receive equal influence before the water mode is combined with road
and air. This hierarchical construction prevents the water mode from receiving
additional influence merely because it is represented by more source
indicators.
