# Audit of contextual population and police data

This audit separates the primary municipal-capacity model from contextual evidence on violence against women.

## Sources and coverage

Female population comes from IBGE SIDRA table 9514 (variable 93, sex classification 5, year 2022). The extraction returns all 144 municipalities of Pará and 4,068,318 women.

The four police workbooks supplied for this study contain 642,281 records:

| Year | Source rows | Female-victim rows |
|---:|---:|---:|
| 2022 | 170,649 | 71,797 |
| 2023 | 166,749 | 69,180 |
| 2024 | 156,945 | 65,711 |
| 2025 | 148,938 | 59,970 |

The label `ALTAMIRA/CASTELO DOS SONHOS` is consolidated into Altamira. This converts the 145 territorial labels in each source file into the 144 official municipalities. `ELDORADO DOS CARAJAS` is matched to the official IBGE name `Eldorado do Carajás`.

## Outputs

- `data/processed/contextual/ibge_female_population_2022_pa.csv`: female population and IBGE municipality codes.
- `data/processed/contextual/police_municipal_year_2022_2025_pa.csv`: municipality-year counts.
- `data/processed/contextual/contextual_vaw_municipal_year_2022_2025_pa.csv`: audited counts and rates per 100,000 women.
- `data/processed/contextual_vaw_data_audit.json`: source hashes and machine-readable checks.
- `scripts/build_contextual_vaw_data.py`: processing code.

The raw police workbooks are not committed because they contain individual-level age, location, and other record attributes. Their SHA-256 hashes are recorded in the audit.

## Classification rules

The focused contextual measure includes female-victim records classified as:

- bodily injury with an explicit domestic-violence specification;
- rape;
- rape of a vulnerable person;
- feminicide, whether represented as a direct consolidated category or as a homicide specification;
- explicit attempted feminicide.

Feminicide remains a separate supplementary outcome because rare municipal counts and structural zeros limit comparison. The broad `all_female_records` field is retained for source auditing, but it includes offenses outside the study focus and must not be interpreted as violence-against-women incidence.

Exact duplicate rows are retained. The workbooks have no unique occurrence identifier, so equality across exported fields is not sufficient evidence that two records represent the same event.

## Scientific use

Population and police records are contextual variables and do not enter the primary score. The new tables do not change indicators, normalization, weights, scores, ranks, or profiles.

Administrative records do not estimate incidence, hidden violence, individual risk, or underreporting. Municipal differences may also reflect access to reporting, service availability, recording practices, and institutional capacity.

The female population is fixed at the 2022 Census value for annual rate denominators. These rates describe recorded events relative to the female population; they are not estimates of individual probability or annual incidence.


## Contextual relationship with municipal priority

The contextual analysis compares each municipality's four-year mean selected-record rate with the previously calculated capacity-priority outputs. It is descriptive and does not modify the model.

Spearman associations between the mean observed rate and the mean priority score are:

| Method | Spearman correlation |
|---|---:|
| Hierarchical additive | -0.069 |
| PROMETHEE II | -0.052 |
| TOPSIS | -0.039 |

Year-specific associations for the additive score range from -0.0497 to -0.1013. These values indicate little monotonic correspondence between administrative-record rates and capacity-priority scores. The capacity model therefore does not reproduce the ordering of police records.

For descriptive comparison, municipalities are divided using two previously declared or sample-based references: priority in the upper quartile in at least 75% of configurations and a four-year mean observed rate above or below the municipal median. The resulting counts are:

- 12 municipalities: higher capacity-strengthening priority and higher observed rate;
- 13 municipalities: higher capacity-strengthening priority and lower observed rate;
- 60 municipalities: other priority profiles and higher observed rate;
- 59 municipalities: other priority profiles and lower observed rate.

These groups are interpretive cross-tabulations, not new priority classes. In particular, a lower observed rate cannot be interpreted as lower violence, hidden violence, or underreporting.
