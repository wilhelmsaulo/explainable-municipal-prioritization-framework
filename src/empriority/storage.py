from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

import pandas as pd


class ArtifactStore:
    """Persist reproducible outputs, cache entries and timestamped snapshots."""

    def __init__(self, cache_directory: Path, output_directory: Path) -> None:
        self.cache_directory = cache_directory
        self.output_directory = output_directory

    @staticmethod
    def fingerprint(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def cache_paths(self, namespace: str, fingerprint: str) -> tuple[Path, Path]:
        directory = self.cache_directory / namespace
        return directory / f"{fingerprint}.csv", directory / f"{fingerprint}.metadata.json"

    def read_cache(
        self,
        namespace: str,
        fingerprint: str,
    ) -> tuple[pd.DataFrame, dict[str, Any]] | None:
        data_path, metadata_path = self.cache_paths(namespace, fingerprint)
        if not data_path.exists() or not metadata_path.exists():
            return None
        frame = pd.read_csv(data_path, dtype=str)
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["cache_hit"] = True
        return frame, metadata

    def write_cache(
        self,
        namespace: str,
        fingerprint: str,
        frame: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> None:
        data_path, metadata_path = self.cache_paths(namespace, fingerprint)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(data_path, index=False, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    def write_output(
        self,
        name: str,
        frame: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> tuple[Path, Path, Path]:
        safe_name = Path(name).stem
        self.output_directory.mkdir(parents=True, exist_ok=True)
        data_path = self.output_directory / f"{safe_name}.csv"
        metadata_path = self.output_directory / f"{safe_name}.metadata.json"
        frame.to_csv(data_path, index=False, encoding="utf-8")
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        snapshot_directory = self.output_directory / "snapshots" / safe_name / timestamp
        snapshot_directory.mkdir(parents=True, exist_ok=True)
        shutil.copy2(data_path, snapshot_directory / data_path.name)
        shutil.copy2(metadata_path, snapshot_directory / metadata_path.name)
        return data_path, metadata_path, snapshot_directory
