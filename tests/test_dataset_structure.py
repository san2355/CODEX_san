import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")

from hfref_simulator.simulate_visit1 import OUTPUT_COLUMNS, simulate_visit1


def test_columns_match_spec_exactly():
    df, _ = simulate_visit1(n_patients=20, save_csv=False)
    assert list(df.columns) == OUTPUT_COLUMNS
