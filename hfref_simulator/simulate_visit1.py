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
from hfref_simulator.physiology import compute_vitals_labs_expected, sat, sigmoid


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
    "Cr_pct_ch",
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


def _compute_cr_prior_and_pct(cr_prior, egfr_prior, meds, sglt2_recent_start, cfg, rng):
    """Implements requested Cr_prior and Cr_pct_ch design."""
    base_drift = rng.normal(cfg.cr_pct_base_mean, cfg.cr_pct_base_sd, size=cr_prior.shape[0])
    noise = rng.normal(0.0, cfg.cr_pct_noise_sd, size=cr_prior.shape[0])

    raasi_sat = sat(meds["RAASi"], cfg.c_raasi)
    mra_sat = sat(meds["MRA"], cfg.c_mra)

    ckd60 = (egfr_prior < 60).astype(float)
    ckd30 = (egfr_prior < 30).astype(float)

    med_effect = (
        raasi_sat * (cfg.cr_pct_raas_low + cfg.cr_pct_raas_ckd60 * ckd60 + cfg.cr_pct_raas_ckd30 * ckd30)
        + mra_sat * (cfg.cr_pct_mra_low + cfg.cr_pct_mra_ckd60 * ckd60)
    )

    sglt2_bump = np.where(
        (meds["SGLT2i"] == 1) & (sglt2_recent_start == 1),
        rng.uniform(cfg.sglt2_low, cfg.sglt2_high, size=cr_prior.shape[0]),
        0.0,
    )

    wrf_logit = (
        cfg.wrf_b0
        + cfg.wrf_b60 * ckd60
        + cfg.wrf_b30 * ckd30
        + cfg.wrf_b_raas * meds["RAASi"]
        + cfg.wrf_b_mra * meds["MRA"]
        + cfg.wrf_b_combo * ((meds["RAASi"] > 0) & (meds["MRA"] > 0))
    )
    wrf_p = sigmoid(wrf_logit)
    wrf_flag = rng.random(cr_prior.shape[0]) < wrf_p
    rare_wrf_tail = np.where(wrf_flag, rng.uniform(cfg.wrf_mag_low, cfg.wrf_mag_high, size=cr_prior.shape[0]), 0.0)

    cr_pct_ch = np.clip(base_drift + med_effect + sglt2_bump + noise + rare_wrf_tail, *cfg.cr_pct_bounds)

    return cr_prior, cr_pct_ch, wrf_flag.astype(int)


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

    meds = {
        "RAASi": _sample_dose(rng, cfg.p_any_raasi, n_patients, cfg.dose_probs),
        "BB": _sample_dose(rng, cfg.p_any_bb, n_patients, cfg.dose_probs),
        "MRA": _sample_dose(rng, cfg.p_any_mra, n_patients, cfg.dose_probs),
        "SGLT2i": (rng.random(n_patients) < cfg.p_sglt2i).astype(int),
    }
    meds["RAASi_is_ARNI"] = ((meds["RAASi"] > 0) & (rng.random(n_patients) < cfg.p_arni_given_raasi)).astype(int)

    # --- New renal timeline: Cr_prior -> Cr_pct_ch -> Cr_visit1 ---
    cr_prior = np.clip(
        baseline["Cr0"] * rng.lognormal(mean=0.0, sigma=cfg.cr_prior_noise_sigma, size=n_patients),
        *cfg.cr_bounds,
    )
    egfr_prior = np.clip(egfr_ckd_epi_2021(cr_prior, age, sex), *cfg.gfr_bounds)

    sglt2_recent_start = ((meds["SGLT2i"] == 1) & (rng.random(n_patients) < cfg.sglt2_recent_start_prob)).astype(int)
    cr_prior, cr_pct_ch, wrf_flag = _compute_cr_prior_and_pct(
        cr_prior, egfr_prior, meds, sglt2_recent_start, cfg, rng
    )
    cr_visit1 = np.clip(cr_prior * (1.0 + cr_pct_ch / 100.0), *cfg.cr_bounds)
    gfr_visit1 = np.clip(egfr_ckd_epi_2021(cr_visit1, age, sex), *cfg.gfr_bounds)

    effects = {
        "sbp_sens": np.clip(rng.normal(1.0, cfg.sbp_sens_sd, size=n_patients), 0.4, 1.7),
        "hr_sens": np.clip(rng.normal(1.0, cfg.hr_sens_sd, size=n_patients), 0.5, 1.8),
        "hyperk_sens": np.clip(rng.normal(1.0, cfg.hyperk_sens_sd, size=n_patients), 0.5, 1.8),
    }

    baseline["eGFR_prior"] = egfr_prior
    baseline["eGFR_visit1"] = gfr_visit1
    expected = compute_vitals_labs_expected(baseline, meds, effects, cfg, rng)

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
            "Cr": cr_visit1,
            "Cr_pct_ch": cr_pct_ch,
            "GFR": gfr_visit1,
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
                "Cr_prior": cr_prior,
                "Cr0": baseline["Cr0"],
                "eGFR_prior": egfr_prior,
                "RAASi_is_ARNI": meds["RAASi_is_ARNI"],
                "WRF_event": wrf_flag,
            }
        )
        return out, home_df, latent

    return out, home_df


def calibration_report(n_patients=500, cfg=None):
    cfg = cfg or SimulatorConfig()
    df, _, latent = simulate_visit1(n_patients=n_patients, cfg=cfg, save_csv=False, return_latent=True)
    merged = df.merge(latent, on="Pat_ID", how="left")

    c = merged["Cr_pct_ch"]
    q25, q75 = np.quantile(c, [0.25, 0.75])

    s1 = merged["eGFR_prior"] < 30
    s2 = (merged["eGFR_prior"] >= 30) & (merged["eGFR_prior"] < 60)
    s3 = merged["eGFR_prior"] >= 60

    wrf_rate_s1 = float((merged.loc[s1, "Cr_pct_ch"] >= 30).mean()) if s1.any() else 0.0
    wrf_rate_s2 = float((merged.loc[s2, "Cr_pct_ch"] >= 30).mean()) if s2.any() else 0.0
    wrf_rate_s3 = float((merged.loc[s3, "Cr_pct_ch"] >= 30).mean()) if s3.any() else 0.0

    return {
        "cr_pct_ch_mean": float(c.mean()),
        "cr_pct_ch_median": float(c.median()),
        "cr_pct_ch_iqr": [float(q25), float(q75)],
        "pct_cr_pct_ch_ge_30": float((c >= 30).mean()),
        "pct_cr_pct_ch_ge_30_egfr_prior_lt30": wrf_rate_s1,
        "pct_cr_pct_ch_ge_30_egfr_prior_30_59": wrf_rate_s2,
        "pct_cr_pct_ch_ge_30_egfr_prior_ge60": wrf_rate_s3,
        "wrf_monotonic_low_egfr_higher_rate": bool(wrf_rate_s1 >= wrf_rate_s2 >= wrf_rate_s3),
        "k_gt_5_5_overall": float((merged["K"] > 5.5).mean()),
        "k_gt_6_0_overall": float((merged["K"] > 6.0).mean()),
        "k_gt_5_5_mra": float((merged.loc[merged["MRA"] > 0, "K"] > 5.5).mean()) if (merged["MRA"] > 0).any() else 0.0,
        "symptomatic_hypotension_rate": float(merged["Sx_hypot"].mean()),
        "med_any_raasi": float((merged["RAASi"] > 0).mean()),
        "med_arni_overall": float(merged["RAASi_is_ARNI"].mean()),
        "med_arni_given_raasi": float(merged.loc[merged["RAASi"] > 0, "RAASi_is_ARNI"].mean()) if (merged["RAASi"] > 0).any() else 0.0,
        "med_any_bb": float((merged["BB"] > 0).mean()),
        "med_any_mra": float((merged["MRA"] > 0).mean()),
        "med_any_sglt2i": float((merged["SGLT2i"] > 0).mean()),
    }


if __name__ == "__main__":
    df, _ = simulate_visit1(n_patients=10)
    print(df.head())
    print("\nCalibration snapshot:")
    print(calibration_report(500))
