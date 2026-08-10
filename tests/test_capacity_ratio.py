import pandas as pd

from empriority.capacity_input_audit import _materialize_indicator
from empriority.integrated_priority import _indicator_values


DEFINITION = {
    "column": "institutional_deficit_available_4",
    "direction": "benefit",
    "transformation": "observed_ratio",
    "denominator_column": "institutional_coverage",
    "output_column": "institutional_deficit_ratio",
}


def test_institutional_ratio_uses_only_observed_item_coverage() -> None:
    frame = pd.DataFrame(
        {
            "institutional_deficit_available_4": [2, 2, 3],
            "institutional_coverage": [2, 4, 4],
        }
    )

    values = _indicator_values(frame, DEFINITION)

    assert values.name == "institutional_deficit_ratio"
    assert values.tolist() == [1.0, 0.5, 0.75]


def test_input_audit_materializes_same_published_ratio() -> None:
    frame = pd.DataFrame(
        {
            "institutional_deficit_available_4": [0, 1, 2],
            "institutional_coverage": [2, 2, 4],
        }
    )

    column, values = _materialize_indicator(frame, DEFINITION)

    assert column == "institutional_deficit_ratio"
    assert values.tolist() == [0.0, 0.5, 0.5]
