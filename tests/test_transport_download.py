from empriority.transport_accessibility.catalog import SOURCES


def test_mapbiomas_road_sources_use_exact_registered_urls() -> None:
    expected_files = {
        "mapbiomas_state_roads": "rodovia-estadual.zip",
        "mapbiomas_federal_roads": "rodovia-federal.zip",
        "mapbiomas_other_roads": "outros-trechos.zip",
    }
    sources = {source["source_id"]: source for source in SOURCES}

    for source_id, filename in expected_files.items():
        source = sources[source_id]
        assert source["direct_urls_only"] is True
        assert len(source["direct_urls"]) == 1
        assert source["direct_urls"][0].endswith(filename)
        assert source["expected_sha256"]
