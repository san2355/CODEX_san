import numpy as np


def egfr_ckd_epi_2021(scr_mg_dl, age, sex):
    """Compute CKD-EPI 2021 creatinine-only eGFR (race-free).

    sex should be 'F'/'M' or female/male-like strings.
    """
    scr = np.asarray(scr_mg_dl, dtype=float)
    age_arr = np.asarray(age, dtype=float)
    sex_arr = np.asarray(sex)

    female_mask = np.char.lower(sex_arr.astype(str)).astype("U16")
    female_mask = np.isin(female_mask, ["f", "female"])

    kappa = np.where(female_mask, 0.7, 0.9)
    alpha = np.where(female_mask, -0.241, -0.302)
    sex_factor = np.where(female_mask, 1.012, 1.0)

    ratio = scr / kappa
    min_term = np.minimum(ratio, 1.0) ** alpha
    max_term = np.maximum(ratio, 1.0) ** (-1.200)

    egfr = 142.0 * min_term * max_term * (0.9938 ** age_arr) * sex_factor
    return egfr
