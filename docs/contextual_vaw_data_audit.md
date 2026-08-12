# Audit of contextual population and police data

This audit separates the primary municipal-capacity model from contextual evidence on violence against women.

## Findings

- The primary model remains unchanged. Population and police records are not scoring criteria.
- The repository contains all 144 municipal rows in `data/processed/police_aggregated_2022_2025_pa.csv`, and every row reports four observed years.
- The police file is a four-year municipal aggregate. The annual source files are not present in `data/source` or `data/manual`; therefore, annual trends and persistence cannot be reproduced from the current `main` branch.
- The integrated matrix contains `population_2023`, documented as total population from the 2022 Demographic Census released or processed in 2023. It does not contain female population.
- Existing police rate fields use total population as denominator. They must not be described as rates per 100,000 women.

## Scientific use

The police aggregate may support labelled descriptive and sensitivity analyses. It cannot estimate incidence, hidden violence, individual risk, or underreporting. Municipal differences may also reflect access to reporting, availability of services, administrative recording, and institutional capacity.

Feminicide is retained only as a supplementary descriptive outcome because rare municipal counts and structural zeros limit its use for comparison.

## Inputs still required

1. Official IBGE 2022 Census female population for all 144 municipalities, with the table identifier, source URL, and extraction date.
2. The four original police files (2022–2025), or an audited municipality–year–category table with provenance metadata.

Until these inputs are restored and audited, the contextual analysis must not report rates per 100,000 women, annual trends, or persistence.
