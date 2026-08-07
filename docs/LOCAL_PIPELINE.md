# Local pipeline execution

The dataset finalization and audit can be executed without GitHub Actions.

## Requirements

- Python 3.11 or newer;
- a complete clone of this repository;
- `data/processed/integrated_municipal_matrix.csv` present locally.

## Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
python scripts/run_pipeline.py --stage finalize
```

## Linux or macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
python scripts/run_pipeline.py --stage finalize
```

## Expected result

A successful run prints `PIPELINE COMPLETED` and updates:

- `data/processed/integrated_municipal_matrix.csv`;
- `data/processed/integrated_matrix_audit.json`;
- `data/processed/integrated_matrix_column_profile.csv`;
- `data/processed/modeling_readiness_columns.csv`;
- `data/processed/modeling_readiness_status.json`;
- `data/processed/dataset_finalization_status.json`.

A failed run prints `PIPELINE FAILED` followed by the exception type and message.

GitHub Actions calls this same script, so local and automated execution use the same code path.
