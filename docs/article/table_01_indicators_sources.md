# Table I. Active indicators, sources, and analytical roles

| Macro-dimension | Component | Operational indicator | Source / reference | Acquisition or registration | Direction after alignment | Coverage |
|---|---|---|---|---|---|---:|
| Institutional deficit | Institutional capacity | Proportion of negative responses among the two to four women's-policy institutional items actually observed; unavailable responses are neither deficits nor part of the denominator | IBGE MUNIC 2023 | Aug. 4, 2026 | Higher deficit proportion = greater priority | 144/144 |
| Service-network deficit | Health services | Absence count for UBS, hospitals, CAPS, and emergency units (0--4; observed 0--3) | CNES, June 2026 competence | Aug. 4, 2026 | More absent types = greater priority | 144/144 |
| Service-network deficit | Health workforce | Absence count for physicians, nurses, psychologists, and social workers (0--4; observed 0--2) | CNES, June 2026 competence | Aug. 5, 2026 | More absent categories = greater priority | 144/144 |
| Service-network deficit | Social protection | Absence of a CREAS unit | MDS/SNAS RMA live administrative directory | Aug. 5, 2026 | Absence = greater priority | 144/144 |
| Service-network deficit | Justice | Absence of mapped local TJPA access | TJPA Balcão Virtual live administrative directory | Aug. 5, 2026 | Absence = greater priority | 144/144 |
| Service-network deficit | Specialized protection network | Diversity of validated mapped service categories (0--8 observed) | Ligue 180 live service panel; manual transcription and curated validation | Aug. 6, 2026 | Fewer categories = greater priority | 144/144 |
| Service-network deficit | Specialized protection network | Validated specialized non-health services (0--15 observed) | Ligue 180 live service panel; manual transcription and curated validation | Aug. 6, 2026 | Fewer services = greater priority | 144/144 |
| Transport barrier | Multimodal access | One minus the access score under each of 12 predeclared transport scenarios | MapBiomas roads 2023; ANTAQ ports/crossings 2025 and navigated waterways 2022; DECEA/ICA aerodromes 2026 | Aug. 7, 2026 | Lower access = greater priority | 144/144 in every scenario |

## Aggregation notes

The institutional count is first divided by its observed-item coverage. All
resulting indicators are then converted to within-sample percentile ranks on
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
capacity-priority criteria. For live administrative directories and panels,
the table reports the reproducible acquisition date rather than assigning an
unsupported historical reference year.

## Provenance evidence

- MUNIC 2023 indicators were stored on Aug. 4, 2026.
- The CNES archive is `BASE_DE_DADOS_CNES_202606.ZIP`; establishment indicators
  were stored on Aug. 4 and professional indicators on Aug. 5, 2026.
- MDS/SNAS RMA and TJPA snapshots were stored on Aug. 5, 2026.
- The complete Ligue 180 transcription was stored and documented on Aug. 6,
  2026; 111 records were retained, 105 of which passed primary validation.
- The transport-source catalog was checked on Aug. 7, 2026. Its registered
  reference years are 2023 for MapBiomas roads, 2025 for ANTAQ ports and
  crossings, 2022 for navigated waterways, and 2026 for DECEA/ICA aerodromes.
- ANAC is not an active source because the official DECEA/ICA aerodrome layer
  supplies the aviation geometry used by the model.
