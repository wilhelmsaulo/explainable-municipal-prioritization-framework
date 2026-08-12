# Dashboard

This read-only Streamlit application presents the 48 precomputed configurations
of the multicriteria model for municipal prioritization of response capacity to
violence against women in Pará. It does not recalculate scores or expose
arbitrary weights.

The dashboard combines three dimensions in every configuration:

1. institutional capacity;
2. service-network availability;
3. multimodal accessibility.

Female population from the 2022 Demographic Census and police records from
2022--2025 support contextual and sensitivity analyses. They are not criteria
in the primary score, and police records are not interpreted as violence
incidence or underreporting.

## Run locally

```bash
python -m pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

The application validates that all 144 municipalities and all 48 complete
score/rank pairs are present before rendering.

Streamlit Community Cloud discovers `dashboard/requirements.txt` next to the
entrypoint and installs the visualization dependencies automatically.
