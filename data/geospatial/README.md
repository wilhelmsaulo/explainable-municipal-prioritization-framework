# Municipal boundary visualization layer

`pa_municipal_boundaries_2022_simplified.geojson` is a web-optimized derivative
of the official **IBGE Municipal Digital Mesh 2022** for Pará.

- Source: `PA_Municipios_2022.zip`
- Official URL: <https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/UFs/PA/PA_Municipios_2022.zip>
- Territorial reference: 2022
- Reference system: SIRGAS 2000, geographic coordinates
- Original archive SHA-256: `b5ce6e307290d195e32e5d90866c14d852e67fdb911ec0c75af7556aea539f86`
- Simplified GeoJSON SHA-256: `9fa9b74cf14d755bd24e8078ad840d7cccd0202ecc403de9e680c0f06ed1aed6`
- Features: 144 municipalities

The geometry was cleaned and simplified to 2% with shape preservation, and
coordinates were rounded to four decimal places using Mapshaper. Only
`CD_MUN`, `NM_MUN`, and `SIGLA_UF` were retained. This derivative is used only
for interactive visualization; it does not enter any framework calculation.

The dashboard data contract asserts an exact match between all 144 IBGE
municipality codes in this file and the 144 municipalities in the audited
framework outputs.
