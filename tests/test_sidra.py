from __future__ import annotations

import httpx
import respx

from empriority.connectors.sidra import SidraConnector, SidraQuery


def test_build_url_orders_classifications() -> None:
    connector = SidraConnector("https://apisidra.ibge.gov.br/values")
    query = SidraQuery(
        table=4709,
        territorial_level=6,
        territories="all/in/n3/15",
        variables="93",
        periods="2022",
        classifications={58: "1140", 2: "4,5"},
    )

    assert connector.build_url(query) == (
        "https://apisidra.ibge.gov.br/values/t/4709/n6/all/in/n3/15/v/93/p/2022/c2/4,5/c58/1140"
    )


@respx.mock
def test_fetch_normalizes_sidra_header_and_records_metadata() -> None:
    connector = SidraConnector("https://apisidra.ibge.gov.br/values")
    query = SidraQuery(table=4709, territorial_level=6, periods="2022")
    url = connector.build_url(query)
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"NC": "Nível Territorial (Código)", "NN": "Nível Territorial", "V": "Valor"},
                {"NC": "6", "NN": "Município", "V": "12345"},
            ],
        )
    )

    frame, metadata = connector.fetch(query)

    assert frame.to_dict(orient="records") == [
        {
            "nivel_territorial_codigo": "6",
            "nivel_territorial": "Município",
            "valor": "12345",
        }
    ]
    assert metadata.source == "IBGE SIDRA"
    assert metadata.endpoint == url
    assert metadata.record_count == 1
    assert metadata.parameters["table"] == 4709
    assert metadata.column_labels["valor"] == "Valor"


def test_normalize_empty_payload() -> None:
    frame, labels = SidraConnector._normalize([])

    assert frame.empty
    assert labels == {}
