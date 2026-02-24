from dataclasses import dataclass


@dataclass
class SimulatorConfig:
    seed: int = 42
    n_days_home: int = 14
    readings_per_day: int = 2

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

    # Medication assignment probabilities
    p_any_raasi: float = 0.82
    p_any_bb: float = 0.88
    p_any_mra: float = 0.55
    p_sglt2i: float = 0.72

    # Dose intensity probabilities for 1..4 when medication is present
    dose_probs: tuple = (0.35, 0.30, 0.22, 0.13)

    # Saturation constants
    c_raasi: float = 1.6
    c_bb: float = 1.4
    c_mra: float = 1.5
    c_sglt2i: float = 1.0

    # Expected physiologic effects at full saturation
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

    # Random effect SDs
    sbp_sens_sd: float = 0.20
    hr_sens_sd: float = 0.18
    renal_sens_sd: float = 0.25
    hyperk_sens_sd: float = 0.22

    # Home monitoring dynamics
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

    # Logistic model intercepts (calibration knobs)
    hyperk_spike_intercept: float = -4.7
    wrf_intercept: float = -4.3
    sx_hypot_intercept: float = -2.95
    sx_brady_intercept: float = -3.15

    # Logistic slopes (calibration knobs)
    hyperk_slope_egfr_low: float = 0.055
    hyperk_slope_raasi: float = 0.40
    hyperk_slope_mra: float = 0.75
    hyperk_slope_combo: float = 0.25

    wrf_slope_egfr_low: float = 0.05
    wrf_slope_raasi: float = 0.38
    wrf_slope_mra: float = 0.22

    sx_tir_scale: float = 0.11
    sx_tir_midpoint: float = 10.0


    # Doctor Brain protocol thresholds
    TIR_HI: float = 10.0
    K_HOLD: float = 5.5
    K_MRA_INIT: float = 5.0
    K_MRA_UP: float = 5.0
    GFR_MRA_MIN: float = 30.0
    GFR_SGLT2_MIN: float = 25.0
    CR_PCT_HOLD: float = 50.0

    visit_number: int = 1
