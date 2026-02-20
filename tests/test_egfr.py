import pytest

np = pytest.importorskip("numpy")

from hfref_simulator.egfr import egfr_ckd_epi_2021


def test_egfr_decreases_when_creatinine_increases():
    age = np.array([65, 65, 65])
    sex = np.array(["M", "M", "M"])
    cr = np.array([0.9, 1.3, 1.8])
    gfr = egfr_ckd_epi_2021(cr, age, sex)
    assert gfr[0] > gfr[1] > gfr[2]
