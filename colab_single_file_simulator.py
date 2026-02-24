"""
Single-file, Colab-ready HFrEF Visit-1 simulator.
Copy/paste this whole file into one Colab cell and run.
It will generate:
  - visit_table.csv
  - home_readings.csv
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class SimulatorConfig:
    seed: int = 42
    n_days_home: int = 14
    low_sbp_threshold: float = 90.0
    low_hr_threshold: float = 50.0

    clinic_sbp_bounds: tuple = (70.0, 180.0)
    clinic_hr_bounds: tuple = (35.0, 130.0)
    k_bounds: tuple = (3.0, 6.8)
    cr_bounds: tuple = (0.5, 4.0)
    gfr_bounds: tuple = (5.0, 140.0)

    age_bounds: tuple = (45, 85)
    baseline_sbp_bounds: tuple = (95.0, 140.0)
    baseline_hr_bounds: tuple = (65.0, 105.0)
    baseline_cr_bounds: tuple = (0.8, 2.2)
    baseline_k_bounds: tuple = (3.6, 5.2)

    p_any_raasi: float = 0.82
    p_any_bb: float = 0.88
    p_any_mra: float = 0.55
    p_sglt2i: float = 0.72
    dose_probs: tuple = (0.35, 0.30, 0.22, 0.13)

    c_raasi: float = 1.6
    c_bb: float = 1.4
    c_mra: float = 1.5
    c_sglt2i: float = 1.0

    raasi_sbp_drop: float = -10.0
    raasi_cr_rise: float = 0.12
    raasi_k_rise: float = 0.18
    bb_hr_drop: float = -18.0
    bb_sbp_drop: float = -4.0
    mra_sbp_drop: float = -2.5
    mra_cr_rise: float = 0.10
    mra_k_rise: float = 0.32
    sglt2i_sbp_drop: float = -3.0
    sglt2i_cr_rise: float = 0.03

    sbp_sens_sd: float = 0.20
    hr_sens_sd: float = 0.18
    renal_sens_sd: float = 0.25
    hyperk_sens_sd: float = 0.22

    home_day_noise_sbp: float = 5.5
    home_day_noise_hr: float = 4.5
    home_ampm_sbp: float = 3.0
    home_ampm_hr: float = 2.5
    home_outlier_prob: float = 0.02
    home_missing_prob: float = 0.08

    whitecoat_sbp_mean: float = 4.0
    whitecoat_sbp_sd: float = 4.0
    clinic_hr_offset_mean: float = 1.0
    clinic_hr_offset_sd: float = 2.0

    hyperk_spike_intercept: float = -4.7
    wrf_intercept: float = -4.3
    sx_hypot_intercept: float = -2.95
    sx_brady_intercept: float = -3.15

    hyperk_slope_egfr_low: float = 0.055
    hyperk_slope_raasi: float = 0.40
    hyperk_slope_mra: float = 0.75
    hyperk_slope_combo: float = 0.25
    wrf_slope_egfr_low: float = 0.05
    wrf_slope_raasi: float = 0.38
    wrf_slope_mra: float = 0.22

    sx_tir_scale: float = 0.11
    sx_tir_midpoint: float = 10.0
    visit_number: int = 1


def egfr_ckd_epi_2021(scr_mg_dl, age, sex):
    scr = np.asarray(scr_mg_dl, dtype=float)
    age_arr = np.asarray(age, dtype=float)
    sex_arr = np.asarray(sex)
    female = np.isin(np.char.lower(sex_arr.astype(str)).astype("U16"), ["f", "female"])
    kappa = np.where(female, 0.7, 0.9)
    alpha = np.where(female, -0.241, -0.302)
    sex_factor = np.where(female, 1.012, 1.0)
    ratio = scr / kappa
    return 142.0 * (np.minimum(ratio, 1.0) ** alpha) * (np.maximum(ratio, 1.0) ** (-1.200)) * (0.9938 ** age_arr) * sex_factor


def sat(dose, c):
    return 1.0 - np.exp(-np.asarray(dose, dtype=float) / c)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def _trunc_normal(rng, mean, sd, low, high, n):
    return np.clip(rng.normal(mean, sd, size=n), low, high)


def _sample_dose(rng, p_any, n, dose_probs):
    present = rng.random(n) < p_any
    dose = np.zeros(n, dtype=int)
    dose[present] = rng.choice(np.arange(1, 5), size=present.sum(), p=dose_probs)
    return dose


def simulate_visit1(n_patients=10, cfg=None, save_csv=True, return_latent=False):
    cfg = cfg or SimulatorConfig()
    rng = np.random.default_rng(cfg.seed)
    ids = np.arange(1, n_patients + 1)

    sex = rng.choice(["M", "F"], size=n_patients, p=[0.62, 0.38])
    age = rng.integers(cfg.age_bounds[0], cfg.age_bounds[1] + 1, size=n_patients)

    sbp0 = _trunc_normal(rng, 116, 12, *cfg.baseline_sbp_bounds, n_patients)
    hr0 = _trunc_normal(rng, 82, 11, *cfg.baseline_hr_bounds, n_patients)
    cr0 = _trunc_normal(rng, 1.25, 0.38, *cfg.baseline_cr_bounds, n_patients)
    k0 = _trunc_normal(rng, 4.25, 0.34, *cfg.baseline_k_bounds, n_patients)
    egfr0 = egfr_ckd_epi_2021(cr0, age, sex)

    raasi = _sample_dose(rng, cfg.p_any_raasi, n_patients, cfg.dose_probs)
    bb = _sample_dose(rng, cfg.p_any_bb, n_patients, cfg.dose_probs)
    mra = _sample_dose(rng, cfg.p_any_mra, n_patients, cfg.dose_probs)
    sglt2i = (rng.random(n_patients) < cfg.p_sglt2i).astype(int)

    sbp_sens = np.clip(rng.normal(1.0, cfg.sbp_sens_sd, size=n_patients), 0.4, 1.7)
    hr_sens = np.clip(rng.normal(1.0, cfg.hr_sens_sd, size=n_patients), 0.5, 1.8)
    renal_sens = np.clip(rng.normal(1.0, cfg.renal_sens_sd, size=n_patients), 0.4, 1.8)
    hyperk_sens = np.clip(rng.normal(1.0, cfg.hyperk_sens_sd, size=n_patients), 0.5, 1.8)

    raasi_s, bb_s, mra_s, sglt_s = sat(raasi, cfg.c_raasi), sat(bb, cfg.c_bb), sat(mra, cfg.c_mra), sat(sglt2i, cfg.c_sglt2i)

    sbp_true = sbp0 + sbp_sens * (cfg.raasi_sbp_drop * raasi_s + cfg.bb_sbp_drop * bb_s + cfg.mra_sbp_drop * mra_s + cfg.sglt2i_sbp_drop * sglt_s) + rng.normal(0, 3.0, n_patients)
    hr_true = hr0 + hr_sens * (cfg.bb_hr_drop * bb_s) + rng.normal(0, 2.5, n_patients)

    ckdf = np.clip((70.0 - egfr0) / 30.0, 0.0, 2.0)
    cr_med_delta = renal_sens * (cfg.raasi_cr_rise * raasi_s * (1.0 + 0.7 * ckdf) + cfg.mra_cr_rise * mra_s * (1.0 + 0.4 * ckdf) + cfg.sglt2i_cr_rise * sglt_s)
    wrf_logit = cfg.wrf_intercept + cfg.wrf_slope_egfr_low * (90.0 - egfr0) + cfg.wrf_slope_raasi * raasi + cfg.wrf_slope_mra * mra
    wrf_flag = rng.random(n_patients) < sigmoid(wrf_logit)
    wrf_multiplier = np.where(wrf_flag, rng.uniform(0.25, 0.55, n_patients), 0.0)
    cr = np.clip(cr0 * (1.0 + cr_med_delta + wrf_multiplier), *cfg.cr_bounds)
    gfr = np.clip(egfr_ckd_epi_2021(cr, age, sex), *cfg.gfr_bounds)

    k_med_delta = hyperk_sens * (cfg.raasi_k_rise * raasi_s + cfg.mra_k_rise * mra_s + 0.10 * raasi_s * mra_s)
    hyperk_logit = cfg.hyperk_spike_intercept + cfg.hyperk_slope_egfr_low * (80.0 - egfr0) + cfg.hyperk_slope_raasi * raasi + cfg.hyperk_slope_mra * mra + cfg.hyperk_slope_combo * ((raasi > 0) & (mra > 0))
    hyperk_flag = rng.random(n_patients) < sigmoid(hyperk_logit)
    k = np.clip(k0 + k_med_delta + np.where(hyperk_flag, rng.normal(0.8, 0.22, n_patients), 0.0), *cfg.k_bounds)

    home_records = []
    for i, pid in enumerate(ids):
        for day in range(cfg.n_days_home):
            ds, dh = rng.normal(0, cfg.home_day_noise_sbp), rng.normal(0, cfg.home_day_noise_hr)
            for tod_idx, tod in enumerate(["AM", "PM"]):
                if rng.random() < cfg.home_missing_prob:
                    continue
                sign = -1.0 if tod_idx == 0 else 1.0
                sbp_h = sbp_true[i] + ds + sign * cfg.home_ampm_sbp + rng.normal(0, 3.0)
                hr_h = hr_true[i] + dh + sign * cfg.home_ampm_hr + rng.normal(0, 2.5)
                if rng.random() < cfg.home_outlier_prob:
                    sbp_h += rng.normal(-18, 6)
                if rng.random() < cfg.home_outlier_prob:
                    hr_h += rng.normal(-14, 5)
                home_records.append({"patient_id": pid, "day": day + 1, "tod": tod, "sbp_home": sbp_h, "hr_home": hr_h})
    home_df = pd.DataFrame(home_records)

    if home_df.empty:
        tir = pd.DataFrame({"Pat_ID": ids, "TIR_low_sys": 0.0, "TIR_low_HR": 0.0})
        clinic = pd.DataFrame({"Pat_ID": ids, "SBP": np.clip(sbp_true, *cfg.clinic_sbp_bounds), "HR": np.clip(hr_true, *cfg.clinic_hr_bounds)})
    else:
        home_df["sbp_low"] = (home_df["sbp_home"] < cfg.low_sbp_threshold).astype(int)
        home_df["hr_low"] = (home_df["hr_home"] < cfg.low_hr_threshold).astype(int)
        a = home_df.groupby("patient_id").agg(n=("sbp_home", "size"), sbp_low=("sbp_low", "sum"), hr_low=("hr_low", "sum"))
        tir = a.assign(TIR_low_sys=100.0 * a["sbp_low"] / a["n"], TIR_low_HR=100.0 * a["hr_low"] / a["n"])[["TIR_low_sys", "TIR_low_HR"]].reset_index().rename(columns={"patient_id": "Pat_ID"})

        clinic_rows = []
        for i, pid in enumerate(ids):
            recent = home_df[(home_df["patient_id"] == pid) & (home_df["day"] >= cfg.n_days_home - 2)]
            m_sbp = recent["sbp_home"].mean() if not recent.empty else sbp_true[i]
            m_hr = recent["hr_home"].mean() if not recent.empty else hr_true[i]
            clinic_rows.append({
                "Pat_ID": pid,
                "SBP": m_sbp + rng.normal(cfg.whitecoat_sbp_mean, cfg.whitecoat_sbp_sd) + rng.normal(0, 3.0),
                "HR": m_hr + rng.normal(cfg.clinic_hr_offset_mean, cfg.clinic_hr_offset_sd) + rng.normal(0, 2.0),
            })
        clinic = pd.DataFrame(clinic_rows)
        clinic["SBP"] = clinic["SBP"].clip(*cfg.clinic_sbp_bounds)
        clinic["HR"] = clinic["HR"].clip(*cfg.clinic_hr_bounds)

    out = pd.DataFrame({
        "Pat_ID": ids,
        "Visit": cfg.visit_number,
        "Age": age,
        "Sex": sex,
        "K": k,
        "Cr": cr,
        "GFR": gfr,
        "Cr_pct_ch": 100.0 * (cr - cr0) / cr0,
        "RAASi": raasi,
        "BB": bb,
        "MRA": mra,
        "SGLT2i": sglt2i,
    }).merge(tir, on="Pat_ID", how="left").merge(clinic, on="Pat_ID", how="left")

    out["TIR_low_sys"] = out["TIR_low_sys"].fillna(0.0).clip(0, 100)
    out["TIR_low_HR"] = out["TIR_low_HR"].fillna(0.0).clip(0, 100)
    out["Sx_hypot"] = (rng.random(n_patients) < sigmoid(cfg.sx_hypot_intercept + cfg.sx_tir_scale * (out["TIR_low_sys"] - cfg.sx_tir_midpoint))).astype(int)
    out["Sx_brady"] = (rng.random(n_patients) < sigmoid(cfg.sx_brady_intercept + cfg.sx_tir_scale * (out["TIR_low_HR"] - cfg.sx_tir_midpoint))).astype(int)

    out = out[["Pat_ID", "Visit", "Age", "Sex", "SBP", "HR", "TIR_low_sys", "TIR_low_HR", "K", "Cr", "Cr_pct_ch", "GFR", "Sx_hypot", "Sx_brady", "RAASi", "BB", "MRA", "SGLT2i"]]

    # Display/output formatting: vitals as whole numbers, labs and renal data to one decimal.
    out["SBP"] = out["SBP"].round(0).astype(int)
    out["HR"] = out["HR"].round(0).astype(int)
    out["TIR_low_sys"] = out["TIR_low_sys"].round(0).astype(int)
    out["TIR_low_HR"] = out["TIR_low_HR"].round(0).astype(int)
    out["K"] = out["K"].round(1)
    out["Cr"] = out["Cr"].round(1)
    out["Cr_pct_ch"] = out["Cr_pct_ch"].round(1)
    out["GFR"] = out["GFR"].round(1)

    if save_csv:
        out.to_csv("visit_table.csv", index=False)
        if home_df.empty:
            pd.DataFrame(columns=["patient_id", "datetime", "sbp_home", "hr_home"]).to_csv("home_readings.csv", index=False)
        else:
            tmp = home_df.copy()
            tmp["datetime"] = pd.to_datetime("2025-01-01") + pd.to_timedelta(tmp["day"] - 1, unit="D") + pd.to_timedelta(np.where(tmp["tod"] == "AM", 8, 20), unit="h")
            tmp[["patient_id", "datetime", "sbp_home", "hr_home"]].to_csv("home_readings.csv", index=False)

    if return_latent:
        latent = pd.DataFrame({"Pat_ID": ids, "Cr0": cr0, "Cr_prior": cr0, "eGFR0": egfr0})
        return out, home_df, latent
    return out, home_df


def calibration_report(n_patients=500, cfg=None):
    cfg = cfg or SimulatorConfig()
    df, _, latent = simulate_visit1(n_patients=n_patients, cfg=cfg, save_csv=False, return_latent=True)
    m = df.merge(latent, on="Pat_ID", how="left")
    cr_rise_30 = ((m["Cr"] - m["Cr0"]) / m["Cr0"]) >= 0.30
    ckd = m["eGFR0"] < 60
    return {
        "symptomatic_hypotension_rate": float(m["Sx_hypot"].mean()),
        "k_gt_5_5_overall": float((m["K"] > 5.5).mean()),
        "k_gt_6_0_overall": float((m["K"] > 6.0).mean()),
        "k_gt_5_5_mra": float((m.loc[m["MRA"] > 0, "K"] > 5.5).mean()) if (m["MRA"] > 0).any() else 0.0,
        "wrf_proxy_cr_rise_ge_30pct_overall": float(cr_rise_30.mean()),
        "wrf_proxy_cr_rise_ge_30pct_ckd": float(cr_rise_30[ckd].mean()) if ckd.any() else 0.0,
        "wrf_proxy_cr_rise_ge_30pct_nonckd": float(cr_rise_30[~ckd].mean()) if (~ckd).any() else 0.0,
    }


# Demo run (N=10), writes CSV artifacts in current directory.
cfg = SimulatorConfig(seed=42)
df, home_df = simulate_visit1(n_patients=10, cfg=cfg, save_csv=True)
print(df.head())
print("\nSummary stats")
print("Mean SBP:", round(df["SBP"].mean(), 1))
print("Mean HR:", round(df["HR"].mean(), 1))
print("% on RAASi:", round((df["RAASi"] > 0).mean() * 100, 1))
print("% on BB:", round((df["BB"] > 0).mean() * 100, 1))
print("% on MRA:", round((df["MRA"] > 0).mean() * 100, 1))
print("% on SGLT2i:", round((df["SGLT2i"] > 0).mean() * 100, 1))
print("% K > 5.5:", round((df["K"] > 5.5).mean() * 100, 1))
print("% Sx_hypot:", round(df["Sx_hypot"].mean() * 100, 1))
print("\nCalibration N=500")
print(calibration_report(n_patients=500, cfg=cfg))
