import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")

from hfref_simulator.config import SimulatorConfig
from hfref_simulator.simulate_visit1 import simulate_visit1


def test_physiologic_bounds():
    cfg = SimulatorConfig(seed=123)
    df, _ = simulate_visit1(n_patients=250, cfg=cfg, save_csv=False)

    assert df["SBP"].between(*cfg.clinic_sbp_bounds).all()
    assert df["HR"].between(*cfg.clinic_hr_bounds).all()
    assert df["K"].between(*cfg.k_bounds).all()
    assert df["Cr"].between(*cfg.cr_bounds).all()
    assert df["GFR"].between(*cfg.gfr_bounds).all()
    assert df["TIR_low_sys"].between(0, 100).all()
    assert df["TIR_low_HR"].between(0, 100).all()
