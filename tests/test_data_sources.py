from __future__ import annotations

import pytest

from empriority.data_sources import (
    DataSourceAlreadyRegisteredError,
    DataSourceManager,
    DataSourceNotFoundError,
)


def test_register_and_run_operation() -> None:
    manager = DataSourceManager()
    manager.register_handler(
        "example.sum",
        lambda left, right: left + right,
        description="Add two values.",
    )

    assert manager.run("EXAMPLE.SUM", 2, 3) == 5
    assert manager.names() == ("example.sum",)
    assert manager.describe() == {"example.sum": "Add two values."}
    assert "example.sum" in manager


def test_duplicate_operation_is_rejected() -> None:
    manager = DataSourceManager()
    manager.register_handler("example.operation", lambda: None)

    with pytest.raises(DataSourceAlreadyRegisteredError):
        manager.register_handler(" example.operation ", lambda: None)


def test_unknown_operation_lists_available_names() -> None:
    manager = DataSourceManager()
    manager.register_handler("known.operation", lambda: None)

    with pytest.raises(DataSourceNotFoundError, match="known.operation"):
        manager.run("missing.operation")


def test_empty_operation_name_is_rejected() -> None:
    manager = DataSourceManager()

    with pytest.raises(ValueError, match="cannot be empty"):
        manager.register_handler("   ", lambda: None)
