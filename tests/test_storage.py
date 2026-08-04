from pathlib import Path

import pandas as pd

from empriority.storage import ArtifactStore


def test_artifact_store_cache_and_snapshot(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "cache", tmp_path / "processed")
    frame = pd.DataFrame({"municipality_code": ["1500107"], "value": [1]})
    metadata = {"source": "test"}
    fingerprint = store.fingerprint({"table": 1})

    store.write_cache("sidra", fingerprint, frame, metadata)
    cached = store.read_cache("sidra", fingerprint)
    assert cached is not None
    cached_frame, cached_metadata = cached
    assert len(cached_frame) == 1
    assert cached_metadata["cache_hit"] is True

    data_path, metadata_path, snapshot_path = store.write_output("example", frame, metadata)
    assert data_path.exists()
    assert metadata_path.exists()
    assert (snapshot_path / data_path.name).exists()
