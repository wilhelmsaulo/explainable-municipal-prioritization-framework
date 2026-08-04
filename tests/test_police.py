from pathlib import Path

from empriority.police import load_police_file


def test_load_police_csv_normalizes_required_columns(tmp_path: Path) -> None:
    source = tmp_path / "police.csv"
    source.write_text(
        "Município,Ano,Tipo de ocorrência,Quantidade\nÓbidos,2022,Ameaça,3\n",
        encoding="utf-8",
    )

    frame = load_police_file(source)
    assert list(frame.columns) == ["municipality", "year", "occurrence_type", "records"]
    assert frame.loc[0, "municipality"] == "Óbidos"
    assert frame.loc[0, "year"] == 2022
    assert frame.loc[0, "records"] == 3
