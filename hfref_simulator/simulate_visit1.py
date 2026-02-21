"""HFrEF Visit-1 simulator.

Usage:
    python -m hfref_simulator.simulate_visit1

Outputs are written to:
  - visit_table.csv
  - home_readings.csv
"""

import numpy as np
import pandas as pd

from hfref_simulator.config import SimulatorConfig
from hfref_simulator.egfr import egfr_ckd_epi_2021
from hfref_simulator.home_monitor import derive_clinic_vitals, simulate_home_monitoring
from hfref_simulator.physiology import compute_vitals_labs_expected, sigmoid


OUTPUT_COLUMNS = [
    "Pat_ID",
    "Visit",
    "Age",
    "Sex",
    "SBP",
    "HR",
    "TIR_low_sys",
    "TIR_low_HR",
    "K",
    "Cr",
    "GFR",
    "Sx_hypot",
    "Sx_brady",
    "RAASi",
    "BB",
    "MRA",
    "SGLT2i",
]


def _trunc_normal(rng, mean, sd, low, high, n):
    x = rng.normal(mean, sd, size=n)
    return np.clip(x, low, high)


def _sample_dose(rng, p_any, n, dose_probs):
    present = rng.random(n) < p_any
    dose = np.zeros(n, dtype=int)
    dose[present] = rng.choice(np.arange(1, 5), size=present.sum(), p=dose_probs)
    return dose


def _logistic_from_tir(tir, intercept, cfg):
    return sigmoid(intercept + cfg.sx_tir_scale * (tir - cfg.sx_tir_midpoint))


def simulate_visit1(n_patients=10, cfg=None, save_csv=True, return_latent=False):
    cfg = cfg or SimulatorConfig()
    rng = np.random.default_rng(cfg.seed)

    pat_ids = np.arange(1, n_patients + 1)
    sex = rng.choice(["M", "F"], size=n_patients, p=[0.62, 0.38])
    age = rng.integers(cfg.age_bounds[0], cfg.age_bounds[1] + 1, size=n_patients)

    baseline = {
        "SBP0": _trunc_normal(rng, 116, 12, *cfg.baseline_sbp_bounds, n=n_patients),
        "HR0": _trunc_normal(rng, 82, 11, *cfg.baseline_hr_bounds, n=n_patients),
        "Cr0": _trunc_normal(rng, 1.25, 0.38, *cfg.baseline_cr_bounds, n=n_patients),
        "K0": _trunc_normal(rng, 4.25, 0.34, *cfg.baseline_k_bounds, n=n_patients),
    }
    baseline["eGFR0"] = egfr_ckd_epi_2021(baseline["Cr0"], age, sex)

    meds = {
        "RAASi": _sample_dose(rng, cfg.p_any_raasi, n_patients, cfg.dose_probs),
        "BB": _sample_dose(rng, cfg.p_any_bb, n_patients, cfg.dose_probs),
        "MRA": _sample_dose(rng, cfg.p_any_mra, n_patients, cfg.dose_probs),
        "SGLT2i": (rng.random(n_patients) < cfg.p_sglt2i).astype(int),
    }

    effects = {
        "sbp_sens": np.clip(rng.normal(1.0, cfg.sbp_sens_sd, size=n_patients), 0.4, 1.7),
        "hr_sens": np.clip(rng.normal(1.0, cfg.hr_sens_sd, size=n_patients), 0.5, 1.8),
        "renal_sens": np.clip(rng.normal(1.0, cfg.renal_sens_sd, size=n_patients), 0.4, 1.8),
        "hyperk_sens": np.clip(rng.normal(1.0, cfg.hyperk_sens_sd, size=n_patients), 0.5, 1.8),
    }

    expected = compute_vitals_labs_expected(baseline, meds, effects, cfg, rng)

    cr = np.clip(expected["Cr_expected"], *cfg.cr_bounds)
    gfr = np.clip(egfr_ckd_epi_2021(cr, age, sex), *cfg.gfr_bounds)
    k = np.clip(expected["K_expected"], *cfg.k_bounds)

    home_df, tir_df = simulate_home_monitoring(
        pat_ids, expected["SBP_true"], expected["HR_true"], cfg, rng
    )

    clinic_df = derive_clinic_vitals(home_df, pat_ids, expected["SBP_true"], expected["HR_true"], cfg, rng)
    clinic_df["SBP"] = clinic_df["SBP"].clip(*cfg.clinic_sbp_bounds)
    clinic_df["HR"] = clinic_df["HR"].clip(*cfg.clinic_hr_bounds)

    out = pd.DataFrame(
        {
            "Pat_ID": pat_ids,
            "Visit": cfg.visit_number,
            "Age": age,
            "Sex": sex,
            "K": k,
            "Cr": cr,
            "GFR": gfr,
            "RAASi": meds["RAASi"],
            "BB": meds["BB"],
            "MRA": meds["MRA"],
            "SGLT2i": meds["SGLT2i"],
        }
    )

    out = out.merge(tir_df, on="Pat_ID", how="left").merge(clinic_df, on="Pat_ID", how="left")
    out["TIR_low_sys"] = out["TIR_low_sys"].fillna(0.0).clip(0, 100)
    out["TIR_low_HR"] = out["TIR_low_HR"].fillna(0.0).clip(0, 100)

    out["Sx_hypot"] = (
        rng.random(n_patients)
        < _logistic_from_tir(out["TIR_low_sys"].to_numpy(), cfg.sx_hypot_intercept, cfg)
    ).astype(int)
    out["Sx_brady"] = (
        rng.random(n_patients)
        < _logistic_from_tir(out["TIR_low_HR"].to_numpy(), cfg.sx_brady_intercept, cfg)
    ).astype(int)

    out = out[OUTPUT_COLUMNS]

    if save_csv:
        out.to_csv("visit_table.csv", index=False)
        if not home_df.empty:
            home_save = home_df.copy()
            home_save["datetime"] = pd.to_datetime("2025-01-01") + pd.to_timedelta(home_save["day"] - 1, unit="D")
            home_save["datetime"] = home_save["datetime"] + pd.to_timedelta(np.where(home_save["tod"] == "AM", 8, 20), unit="h")
            home_save[["patient_id", "datetime", "sbp_home", "hr_home"]].to_csv("home_readings.csv", index=False)
        else:
            pd.DataFrame(columns=["patient_id", "datetime", "sbp_home", "hr_home"]).to_csv("home_readings.csv", index=False)

    if return_latent:
        latent = pd.DataFrame(
            {
                "Pat_ID": pat_ids,
                "Cr0": baseline["Cr0"],
                "eGFR0": baseline["eGFR0"],
            }
        )
        return out, home_df, latent

    return out, home_df


def calibration_report(n_patients=500, cfg=None):
    cfg = cfg or SimulatorConfig()
    df, _, latent = simulate_visit1(n_patients=n_patients, cfg=cfg, save_csv=False, return_latent=True)
    merged = df.merge(latent, on="Pat_ID", how="left")

    cr_rise_30 = ((merged["Cr"] - merged["Cr0"]) / merged["Cr0"]) >= 0.30
    ckd_low = merged["eGFR0"] < 60

    report = {
        "symptomatic_hypotension_rate": float(merged["Sx_hypot"].mean()),
        "k_gt_5_5_overall": float((merged["K"] > 5.5).mean()),
        "k_gt_6_0_overall": float((merged["K"] > 6.0).mean()),
        "k_gt_5_5_mra": float((merged.loc[merged["MRA"] > 0, "K"] > 5.5).mean()) if (merged["MRA"] > 0).any() else 0.0,
        "wrf_proxy_cr_rise_ge_30pct_overall": float(cr_rise_30.mean()),
        "wrf_proxy_cr_rise_ge_30pct_ckd": float(cr_rise_30[ckd_low].mean()) if ckd_low.any() else 0.0,
        "wrf_proxy_cr_rise_ge_30pct_nonckd": float(cr_rise_30[~ckd_low].mean()) if (~ckd_low).any() else 0.0,
    }
    return report


if __name__ == "__main__":
    df, _ = simulate_visit1(n_patients=10)
    print(df.head())
    print("\nCalibration snapshot:")
    print(calibration_report(500))
