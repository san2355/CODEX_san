import pytest

pytest.importorskip("pandas")

import pandas as pd

from hfref_simulator.config import SimulatorConfig
from hfref_simulator.decision_engine import add_doctor_brain_columns, recommend_sequence_titration


def _base_row():
    return {
        "Pat_ID": 1,
        "Visit": 1,
        "SBP": 110,
        "HR": 72,
        "TIR_low_sys": 0.0,
        "TIR_low_HR": 0.0,
        "RAASi": 1,
        "BB": 1,
        "MRA": 1,
        "SGLT2i": 1,
        "K": 4.5,
        "Cr": 1.2,
        "Cr_pct_ch": 5.0,
        "GFR": 55,
        "Sx_hypot": 0,
        "Sx_brady": 0,
    }


def test_brady_scenario_bb_down():
    cfg = SimulatorConfig()
    row = _base_row()
    row["Sx_brady"] = 1
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("BB", -1)
    assert "safety_bradycardia" in crit


def test_hyperk_scenario_mra_down():
    cfg = SimulatorConfig()
    row = _base_row()
    row["K"] = 5.7
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("MRA", -1)
    assert "safety_hyperkalemia" in crit


def test_hypotension_no_brady_raasi_down():
    cfg = SimulatorConfig()
    row = _base_row()
    row["Sx_hypot"] = 1
    row["Sx_brady"] = 0
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("RAASi", -1)
    assert "safety_hypotension" in crit


def test_stable_missing_pillar_initiates_first_eligible():
    cfg = SimulatorConfig()
    row = _base_row()
    row["RAASi"] = 0
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("RAASi", +1)
    assert "initiation" in crit


def test_stable_all_on_uptitrates_first_eligible():
    cfg = SimulatorConfig()
    row = _base_row()
    row["RAASi"] = 2
    row["BB"] = 3
    row["MRA"] = 2
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("RAASi", +1)
    assert "uptitration" in crit


def test_add_columns_schema_and_single_action_per_row():
    cfg = SimulatorConfig()
    df = pd.DataFrame([_base_row(), {**_base_row(), "Pat_ID": 2, "K": 5.8}])
    out = add_doctor_brain_columns(df, cfg)
    assert "Sequence" in out.columns and "titration" in out.columns and "criteria" in out.columns
    assert out["titration"].isin([-1, 0, 1]).all()
    assert ((out["Sequence"] == "NONE") == (out["titration"] == 0)).all()
    assert out["criteria"].astype(str).str.len().gt(0).all()


def test_initiation_priority_first_zero_in_order():
    cfg = SimulatorConfig()
    row = _base_row()
    row["RAASi"] = 2
    row["BB"] = 0
    row["MRA"] = 0
    row["SGLT2i"] = 0
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("BB", +1)
    assert "initiation_priority_order" in crit


def test_uptitration_priority_first_submaximal_in_order_when_all_on():
    cfg = SimulatorConfig()
    row = _base_row()
    row["RAASi"] = 4
    row["BB"] = 2
    row["MRA"] = 1
    row["SGLT2i"] = 1
    seq, tit, crit = recommend_sequence_titration(pd.Series(row), cfg)
    assert (seq, tit) == ("BB", +1)
    assert "uptitration_priority_order" in crit
