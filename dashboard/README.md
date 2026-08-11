# Scientific dashboard

This read-only Streamlit application visualizes the 48 audited framework
configurations. It does not recalculate scores or expose arbitrary weights.

## Run locally

```bash
python -m pip install -e ".[dashboard]"
streamlit run dashboard/app.py
```

The application validates that all 144 municipalities and all 48 complete
score/rank pairs are present before rendering.

Streamlit Community Cloud discovers `dashboard/requirements.txt` next to the
entrypoint and installs the visualization dependencies automatically.
