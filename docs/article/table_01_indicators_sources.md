# Table I. Active indicators, sources, and analytical roles

| Macro-dimension | Component | Operational indicator | Source / reference | Direction after alignment | Coverage |
|---|---|---|---|---|---:|
| Institutional deficit | Institutional capacity | Negative responses among the two to four observed women's-policy institutional items; unavailable responses are not treated as deficits | IBGE MUNIC 2023 | More negative responses = greater priority | 144/144 |
| Service-network deficit | Health services | Absence count for hospitals, CAPS, and emergency units (0--3) | CNES, June 2026 snapshot | More absent types = greater priority | 144/144 |
| Service-network deficit | Health workforce | Absence count for psychologists and social workers (0--2) | CNES, June 2026 snapshot | More absent categories = greater priority | 144/144 |
| Service-network deficit | Social protection | Absence of all mapped specialized social-assistance services (CREAS, Centro POP, Centro-Dia, and shelter units) | MDS/SNAS RMA; snapshot period pending final bibliographic registration | Absence = greater priority | 144/144 |
| Service-network deficit | Justice | Absence of mapped local TJPA access | TJPA; snapshot period pending final bibliographic registration | Absence = greater priority | 144/144 |
| Service-network deficit | Specialized protection network | Diversity of validated mapped service categories (0--8 observed) | Ligue 180 service panel; curated validation; snapshot period pending final bibliographic registration | Fewer categories = greater priority | 144/144 |
| Service-network deficit | Specialized protection network | Validated specialized non-health services (0--15 observed) | Ligue 180 service panel; curated validation; snapshot period pending final bibliographic registration | Fewer services = greater priority | 144/144 |
| Transport barrier | Multimodal access | One minus the access score under each of 12 predeclared transport scenarios | MapBiomas roads (registered as 2023), ANTAQ, and DECEA/ICA; remaining snapshot periods pending final bibliographic registration | Lower access = greater priority | 144/144 in every scenario |

## Aggregation notes

All raw indicators are converted to within-sample percentile ranks on
`[0, 1]`, using average ranks for ties and aligning directions so that higher
values always represent greater relative priority for capacity strengthening.
The two health indicators are averaged within the health component. The two
specialized-protection indicators are averaged within their component. Health,
social protection, justice, and specialized protection then receive equal
influence in the service-network dimension, avoiding implicit overweighting of
components represented by more source variables.

The three macro-dimensions are institutional deficit, service-network deficit,
and transport barrier. Twelve transport scenarios are crossed with four
predeclared macro-weight schemes, producing 48 integrated configurations. The
four schemes are equal dimensions (`1/3, 1/3, 1/3`) and one-at-a-time emphasis
on institutional deficit, service-network deficit, or transport barrier
(`0.50, 0.25, 0.25`). No configuration receives additional frequency weight.

Population from the 2022 Demographic Census, released/processed in 2023, is
used only for provenance and legacy rate fields. Police records for 2022--2025
remain preserved in the broader matrix but are explicitly excluded from the
capacity-priority criteria. Missing source-period metadata identified above
must be resolved from acquisition records before manuscript submission; it is
not inferred here.

