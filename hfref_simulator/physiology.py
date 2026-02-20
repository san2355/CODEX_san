import numpy as np


def sat(dose, c):
    dose = np.asarray(dose, dtype=float)
    return 1.0 - np.exp(-dose / c)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def compute_vitals_labs_expected(baseline, meds, effects, cfg, rng):
    raasi_s = sat(meds["RAASi"], cfg.c_raasi)
    bb_s = sat(meds["BB"], cfg.c_bb)
    mra_s = sat(meds["MRA"], cfg.c_mra)
    sglt_s = sat(meds["SGLT2i"], cfg.c_sglt2i)

    sbp_delta = effects["sbp_sens"] * (
        cfg.raasi_sbp_drop * raasi_s
        + cfg.bb_sbp_drop * bb_s
        + cfg.mra_sbp_drop * mra_s
        + cfg.sglt2i_sbp_drop * sglt_s
    )
    hr_delta = effects["hr_sens"] * (cfg.bb_hr_drop * bb_s)

    sbp_expected = baseline["SBP0"] + sbp_delta + rng.normal(0, 3.0, size=sbp_delta.shape[0])
    hr_expected = baseline["HR0"] + hr_delta + rng.normal(0, 2.5, size=hr_delta.shape[0])

    ckdf = np.clip((70.0 - baseline["eGFR0"]) / 30.0, 0.0, 2.0)
    cr_med_delta = effects["renal_sens"] * (
        cfg.raasi_cr_rise * raasi_s * (1.0 + 0.7 * ckdf)
        + cfg.mra_cr_rise * mra_s * (1.0 + 0.4 * ckdf)
        + cfg.sglt2i_cr_rise * sglt_s
    )

    wrf_logit = (
        cfg.wrf_intercept
        + cfg.wrf_slope_egfr_low * (90.0 - baseline["eGFR0"])
        + cfg.wrf_slope_raasi * meds["RAASi"]
        + cfg.wrf_slope_mra * meds["MRA"]
    )
    wrf_p = sigmoid(wrf_logit)
    wrf_flag = rng.random(size=wrf_p.shape[0]) < wrf_p
    wrf_multiplier = np.where(wrf_flag, rng.uniform(0.25, 0.55, size=wrf_p.shape[0]), 0.0)
    cr_expected = baseline["Cr0"] * (1.0 + cr_med_delta + wrf_multiplier)

    k_med_delta = effects["hyperk_sens"] * (
        cfg.raasi_k_rise * raasi_s
        + cfg.mra_k_rise * mra_s
        + 0.10 * raasi_s * mra_s
    )
    hyperk_logit = (
        cfg.hyperk_spike_intercept
        + cfg.hyperk_slope_egfr_low * (80.0 - baseline["eGFR0"])
        + cfg.hyperk_slope_raasi * meds["RAASi"]
        + cfg.hyperk_slope_mra * meds["MRA"]
        + cfg.hyperk_slope_combo * (meds["RAASi"] > 0) * (meds["MRA"] > 0)
    )
    hyperk_p = sigmoid(hyperk_logit)
    hyperk_flag = rng.random(size=hyperk_p.shape[0]) < hyperk_p
    hyperk_spike = np.where(hyperk_flag, rng.normal(0.8, 0.22, size=hyperk_p.shape[0]), 0.0)
    k_expected = baseline["K0"] + k_med_delta + hyperk_spike

    return {
        "SBP_true": sbp_expected,
        "HR_true": hr_expected,
        "Cr_expected": cr_expected,
        "K_expected": k_expected,
        "wrf_flag": wrf_flag.astype(int),
        "hyperk_flag": hyperk_flag.astype(int),
    }
