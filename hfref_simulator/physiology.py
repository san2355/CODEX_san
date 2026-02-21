import numpy as np


def sat(dose, c):
    dose = np.asarray(dose, dtype=float)
    return 1.0 - np.exp(-dose / c)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def compute_vitals_labs_expected(baseline, meds, effects, cfg, rng):
    """Compute SBP/HR/K at visit-1.

    Cr and eGFR are computed upstream from Cr_prior/Cr_pct_ch design.
    """
    raasi_s = sat(meds["RAASi"], cfg.c_raasi)
    bb_s = sat(meds["BB"], cfg.c_bb)
    mra_s = sat(meds["MRA"], cfg.c_mra)
    sglt_s = sat(meds["SGLT2i"], cfg.c_sglt2i)
    arni_flag = meds.get("RAASi_is_ARNI", np.zeros_like(meds["RAASi"]))

    raasi_sbp_mult = 1.0 + cfg.arni_sbp_extra_multiplier * arni_flag
    raasi_k_mult = 1.0 + cfg.arni_k_extra_multiplier * arni_flag

    sbp_delta = effects["sbp_sens"] * (
        cfg.raasi_sbp_drop * raasi_s * raasi_sbp_mult
        + cfg.bb_sbp_drop * bb_s
        + cfg.mra_sbp_drop * mra_s
        + cfg.sglt2i_sbp_drop * sglt_s
    )
    hr_delta = effects["hr_sens"] * (cfg.bb_hr_drop * bb_s)

    sbp_expected = baseline["SBP0"] + sbp_delta + rng.normal(0, 3.0, size=sbp_delta.shape[0])
    hr_expected = baseline["HR0"] + hr_delta + rng.normal(0, 2.5, size=hr_delta.shape[0])

    egfr_for_hyperk = baseline.get("eGFR_visit1", baseline["eGFR_prior"])

    k_med_delta = effects["hyperk_sens"] * (
        cfg.raasi_k_rise * raasi_s * raasi_k_mult
        + cfg.mra_k_rise * mra_s
        + 0.10 * raasi_s * mra_s
    )
    hyperk_logit = (
        cfg.hyperk_spike_intercept
        + cfg.hyperk_slope_egfr_low * (80.0 - egfr_for_hyperk)
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
        "K_expected": k_expected,
        "hyperk_flag": hyperk_flag.astype(int),
    }
