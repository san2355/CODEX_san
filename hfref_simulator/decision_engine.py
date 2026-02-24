import pandas as pd


ORDER = ["RAASi", "BB", "MRA", "SGLT2i"]


def _stable_bp(row, cfg):
    return int(row.get("Sx_hypot", 0)) == 0 and float(row.get("TIR_low_sys", 0)) <= cfg.TIR_HI


def _stable_hr(row, cfg):
    return int(row.get("Sx_brady", 0)) == 0 and float(row.get("TIR_low_HR", 0)) <= cfg.TIR_HI


def _cr_safe(row, cfg):
    cr_pct = row.get("Cr_pct_ch")
    return pd.isna(cr_pct) or float(cr_pct) < cfg.CR_PCT_HOLD


def _no_change_window(row, cfg):
    tir_hr = float(row.get("TIR_low_HR", 0))
    tir_sbp = float(row.get("TIR_low_sys", 0))
    return (10 < tir_hr < 20) or (10 < tir_sbp < 20)


def _raasi_action(row, cfg):
    cr = float(row.get("Cr", 0))
    cr_pct = row.get("Cr_pct_ch")
    k = float(row.get("K", 0))
    tir_sbp = float(row.get("TIR_low_sys", 0))
    sx_hypot = int(row.get("Sx_hypot", 0))

    if cr >= 3 or ((not pd.isna(cr_pct)) and float(cr_pct) >= 50) or k >= 5.5 or tir_sbp > 10 or sx_hypot == 1:
        return -1, "safety_raasi_protocol_down: RAASi protocol down-titration"

    if _no_change_window(row, cfg) and sx_hypot == 0:
        return 0, "no_change_raasi_protocol"

    if cr < 3 and _cr_safe(row, cfg) and k < 5.5 and tir_sbp <= 10 and sx_hypot == 0:
        return +1, "uptitration_raasi_protocol"

    return 0, "no_change_raasi_protocol"


def _bb_action(row, cfg):
    tir_hr = float(row.get("TIR_low_HR", 0))
    tir_sbp = float(row.get("TIR_low_sys", 0))
    sx_brady = int(row.get("Sx_brady", 0))
    sx_hypot = int(row.get("Sx_hypot", 0))

    if tir_hr > 10 or tir_sbp > 10 or sx_brady == 1 or sx_hypot == 1:
        return -1, "safety_bradycardia/bp_protocol_down: BB protocol down-titration"

    if _no_change_window(row, cfg) and sx_brady == 0 and sx_hypot == 0:
        return 0, "no_change_bb_protocol"

    if tir_hr <= 10 and tir_sbp <= 10 and sx_brady == 0 and sx_hypot == 0:
        return +1, "uptitration_bb_protocol"

    return 0, "no_change_bb_protocol"


def _mra_action(row, cfg):
    sex = str(row.get("Sex", "M"))
    gfr = float(row.get("GFR", 999))
    cr = float(row.get("Cr", 0))
    cr_pct = row.get("Cr_pct_ch")
    k = float(row.get("K", 0))
    tir_sbp = float(row.get("TIR_low_sys", 0))
    sx_hypot = int(row.get("Sx_hypot", 0))
    cr_cutoff = 2.0 if sex.upper().startswith("F") else 2.5

    if gfr <= 30 or cr >= cr_cutoff or ((not pd.isna(cr_pct)) and float(cr_pct) >= 50) or k >= 5.5 or tir_sbp > 10 or sx_hypot == 1:
        return -1, "safety_hyperkalemia/renal/bp_protocol_down: MRA protocol down-titration"

    if _no_change_window(row, cfg) and sx_hypot == 0:
        return 0, "no_change_mra_protocol"

    if gfr > 30 and cr < cr_cutoff and _cr_safe(row, cfg) and k < 5 and tir_sbp <= 10 and sx_hypot == 0:
        return +1, "uptitration_mra_protocol"

    return 0, "no_change_mra_protocol"


def _sglt2_action(row, cfg):
    gfr = float(row.get("GFR", 999))
    tir_sbp = float(row.get("TIR_low_sys", 0))
    sx_hypot = int(row.get("Sx_hypot", 0))

    # NOTE: Source protocol text appears to contain a typo in down-titration criteria.
    # Implemented as clinically consistent with other classes:
    # down-titrate when low-SBP burden is >10 or symptomatic hypotension.
    if gfr <= 25 or tir_sbp > 10 or sx_hypot == 1:
        return -1, "safety_sglt2i_protocol_down: SGLT2i protocol down-titration"

    if _no_change_window(row, cfg) and sx_hypot == 0:
        return 0, "no_change_sglt2i_protocol"

    if gfr > 25 and tir_sbp <= 10 and sx_hypot == 0:
        return +1, "uptitration_sglt2i_protocol"

    return 0, "no_change_sglt2i_protocol"


def recommend_sequence_titration(row, cfg):
    """Protocol-driven rule engine: returns (Sequence, titration, criteria)."""
    raasi = int(row.get("RAASi", 0))
    bb = int(row.get("BB", 0))
    mra = int(row.get("MRA", 0))
    sglt2 = int(row.get("SGLT2i", 0))

    k = float(row.get("K", 0))
    tir_hr = float(row.get("TIR_low_HR", 0))
    tir_sbp = float(row.get("TIR_low_sys", 0))
    sx_brady = int(row.get("Sx_brady", 0))
    sx_hypot = int(row.get("Sx_hypot", 0))

    actions = {
        "RAASi": _raasi_action(row, cfg),
        "BB": _bb_action(row, cfg),
        "MRA": _mra_action(row, cfg),
        "SGLT2i": _sglt2_action(row, cfg),
    }

    # Deterministic protocol safety priorities.
    if (sx_brady == 1 or tir_hr > 10) and bb > 0:
        return "BB", -1, "safety_bradycardia: BB protocol down-titration"

    if k >= 5.5:
        if mra > 0:
            return "MRA", -1, "safety_hyperkalemia: MRA protocol down-titration"
        if raasi > 0:
            return "RAASi", -1, "safety_hyperkalemia: RAASi protocol down-titration"

    if sx_hypot == 1 or tir_sbp > 10:
        if raasi > 0:
            return "RAASi", -1, "safety_hypotension: RAASi protocol down-titration"

    # Apply one recommendation at a time with deterministic priority.
    for med in ORDER:
        dose = {"RAASi": raasi, "BB": bb, "MRA": mra, "SGLT2i": sglt2}[med]
        action, reason = actions[med]
        if dose > 0 and action < 0:
            return med, -1, reason

    # Deliverable rule: if any meds are 0, initiate the first in order at dose step +1.
    for med in ORDER:
        dose = {"RAASi": raasi, "BB": bb, "MRA": mra, "SGLT2i": sglt2}[med]
        if dose == 0:
            return med, +1, f"initiation_priority_order: {med} is first zero-dose pillar"

    # Deliverable rule: if all meds are >=1, up-titrate first in order that is <4.
    for med in ORDER:
        dose = {"RAASi": raasi, "BB": bb, "MRA": mra, "SGLT2i": sglt2}[med]
        if med != "SGLT2i" and 1 <= dose < 4:
            return med, +1, f"uptitration_priority_order: {med} is first submaximal pillar"

    return "NONE", 0, "protocol_no_change: no down-trigger and all pillars at max/maintained"


def add_doctor_brain_columns(df, cfg):
    out = df.copy()
    recs = out.apply(lambda r: recommend_sequence_titration(r, cfg), axis=1)
    out["Sequence"] = recs.apply(lambda x: x[0])
    out["titration"] = recs.apply(lambda x: int(x[1]))
    out["criteria"] = recs.apply(lambda x: x[2])
    return out
