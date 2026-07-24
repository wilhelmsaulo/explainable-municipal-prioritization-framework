import pandas as pd

from empriority.validation import validate_municipalities


def test_valid_municipality_table() -> None:
    frame = pd.DataFrame(
        {
            "municipality_code": ["1500107", "1500206"],
            "municipality_name": ["Abaetetuba", "Acará"],
        }
    )

    result = validate_municipalities(frame, expected_count=2)

    assert result.is_valid
    assert result.observed_count == 2


def test_duplicate_code_is_invalid() -> None:
    frame = pd.DataFrame(
        {
            "municipality_code": ["1500107", "1500107"],
            "municipality_name": ["Abaetetuba", "Abaetetuba"],
        }
    )

    result = validate_municipalities(frame, expected_count=2)

    assert not result.is_valid
    assert result.duplicated_codes == ("1500107",)
