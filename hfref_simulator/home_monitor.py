import numpy as np
import pandas as pd


def simulate_home_monitoring(patient_ids, sbp_true, hr_true, cfg, rng):
    records = []
    n = len(patient_ids)
    for i in range(n):
        for day in range(cfg.n_days_home):
            day_shift_sbp = rng.normal(0.0, cfg.home_day_noise_sbp)
            day_shift_hr = rng.normal(0.0, cfg.home_day_noise_hr)
            for tod_idx, tod_name in enumerate(["AM", "PM"]):
                if rng.random() < cfg.home_missing_prob:
                    continue
                tod_sign = -1.0 if tod_idx == 0 else 1.0
                sbp_val = (
                    sbp_true[i]
                    + day_shift_sbp
                    + tod_sign * cfg.home_ampm_sbp
                    + rng.normal(0, 3.0)
                )
                hr_val = (
                    hr_true[i]
                    + day_shift_hr
                    + tod_sign * cfg.home_ampm_hr
                    + rng.normal(0, 2.5)
                )
                if rng.random() < cfg.home_outlier_prob:
                    sbp_val += rng.normal(-18, 6)
                if rng.random() < cfg.home_outlier_prob:
                    hr_val += rng.normal(-14, 5)
                records.append(
                    {
                        "patient_id": patient_ids[i],
                        "day": day + 1,
                        "tod": tod_name,
                        "sbp_home": sbp_val,
                        "hr_home": hr_val,
                    }
                )

    home_df = pd.DataFrame(records)
    if home_df.empty:
        return home_df, pd.DataFrame({"Pat_ID": patient_ids, "TIR_low_sys": 0.0, "TIR_low_HR": 0.0})

    home_df["sbp_low"] = (home_df["sbp_home"] < cfg.low_sbp_threshold).astype(int)
    home_df["hr_low"] = (home_df["hr_home"] < cfg.low_hr_threshold).astype(int)

    agg = home_df.groupby("patient_id").agg(
        n_obs=("sbp_home", "size"),
        sbp_low=("sbp_low", "sum"),
        hr_low=("hr_low", "sum"),
    )
    agg["TIR_low_sys"] = 100.0 * agg["sbp_low"] / agg["n_obs"]
    agg["TIR_low_HR"] = 100.0 * agg["hr_low"] / agg["n_obs"]
    tir = agg[["TIR_low_sys", "TIR_low_HR"]].reset_index().rename(columns={"patient_id": "Pat_ID"})

    return home_df, tir


def derive_clinic_vitals(home_df, patient_ids, sbp_true, hr_true, cfg, rng):
    clinic = []
    for i, pid in enumerate(patient_ids):
        subset = home_df[(home_df["patient_id"] == pid) & (home_df["day"] >= cfg.n_days_home - 2)]
        if subset.empty:
            base_sbp = sbp_true[i]
            base_hr = hr_true[i]
        else:
            base_sbp = subset["sbp_home"].mean()
            base_hr = subset["hr_home"].mean()

        clinic_sbp = base_sbp + rng.normal(cfg.whitecoat_sbp_mean, cfg.whitecoat_sbp_sd) + rng.normal(0, 3.0)
        clinic_hr = base_hr + rng.normal(cfg.clinic_hr_offset_mean, cfg.clinic_hr_offset_sd) + rng.normal(0, 2.0)
        clinic.append({"Pat_ID": pid, "SBP": clinic_sbp, "HR": clinic_hr})

    return pd.DataFrame(clinic)
