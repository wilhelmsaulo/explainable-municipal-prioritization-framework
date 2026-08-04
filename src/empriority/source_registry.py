from __future__ import annotations

from empriority.config import Settings
from empriority.connectors.ibge_localities import IBGELocalitiesConnector
from empriority.connectors.sidra import SidraConnector
from empriority.data_sources import DataSourceManager


def build_data_source_manager(settings: Settings) -> DataSourceManager:
    """Create the registry of enabled official-source operations."""

    manager = DataSourceManager()

    localities_source = settings.sources.ibge_localities
    if localities_source.enabled:
        localities = IBGELocalitiesConnector(
            base_url=str(localities_source.base_url),
            timeout=settings.runtime.request_timeout_seconds,
        )
        manager.register_handler(
            "ibge.localities.municipalities",
            localities.fetch_municipalities,
            description="Municipal hierarchy from the official IBGE Localities API.",
        )

    sidra_source = settings.sources.sidra
    if sidra_source.enabled:
        sidra = SidraConnector(
            base_url=str(sidra_source.base_url),
            timeout=settings.runtime.request_timeout_seconds,
        )
        manager.register_handler(
            "ibge.sidra.values",
            sidra.fetch,
            description="Tabular values from the official IBGE SIDRA API.",
        )

    return manager
