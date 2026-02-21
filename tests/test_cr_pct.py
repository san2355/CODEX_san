import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("pandas")

from hfref_simulator.simulate_visit1 import simulate_visit1


def test_cr_pct_change_matches_cr_prior_and_visit1():
    df, _, latent = simulate_visit1(n_patients=100, save_csv=False, return_latent=True)
    merged = df.merge(latent[["Pat_ID", "Cr_prior"]], on="Pat_ID", how="left")
    recomputed = ((merged["Cr"] - merged["Cr_prior"]) / merged["Cr_prior"]) * 100.0
    assert np.allclose(recomputed.to_numpy(), merged["Cr_pct_ch"].to_numpy(), atol=1e-6)
