import pandas as pd


ORDER = ["RAASi", "BB", "MRA", "SGLT2i"]


def _stable_bp(row, cfg):
    return int(row.get("Sx_hypot", 0)) == 0 and float(row.get("TIR_low_sys", 0)) <= cfg.TIR_HI


def _stable_hr(row, cfg):
    return int(row.get("Sx_brady", 0)) == 0 and float(row.get("TIR_low_HR", 0)) <= cfg.TIR_HI


def _cr_safe(row, cfg):
    cr_pct = row.get("Cr_pct_ch")
    return pd.isna(cr_pct) or float(cr_pct) < cfg.CR_PCT_HOLD


def recommend_sequence_titration(row, cfg):
    """Deterministic v1 rule engine: returns (Sequence, titration, criteria)."""
    raasi = int(row.get("RAASi", 0))
    bb = int(row.get("BB", 0))
    mra = int(row.get("MRA", 0))
    sglt2 = int(row.get("SGLT2i", 0))

    k = float(row.get("K", 0))
    gfr = float(row.get("GFR", 999))
    cr_pct = row.get("Cr_pct_ch")
    sx_brady = int(row.get("Sx_brady", 0))
    sx_hypot = int(row.get("Sx_hypot", 0))
    tir_hr = float(row.get("TIR_low_HR", 0))
    tir_sbp = float(row.get("TIR_low_sys", 0))

    # A/B) Safety overrides (top-level deterministic priority)
    if (sx_brady == 1 or tir_hr > cfg.TIR_HI) and bb > 0:
        return "BB", -1, "safety_bradycardia: symptomatic brady/low-HR burden with BB on-board"

    if k >= cfg.K_HOLD:
        if mra > 0:
            return "MRA", -1, f"safety_hyperkalemia: K={k:.2f} >= K_HOLD={cfg.K_HOLD}, prioritize MRA down"
        if raasi > 0:
            return "RAASi", -1, f"safety_hyperkalemia: K={k:.2f} >= K_HOLD={cfg.K_HOLD}, RAASi down"

    if sx_hypot == 1 or tir_sbp > cfg.TIR_HI:
        if raasi > 0:
            return "RAASi", -1, "safety_hypotension: symptomatic/low-SBP burden, RAASi-first down"
        if bb > 0:
            return "BB", -1, "safety_hypotension: symptomatic/low-SBP burden, BB down"
        if mra > 0:
            return "MRA", -1, "safety_hypotension: symptomatic/low-SBP burden, MRA down"
        if sglt2 > 0:
            return "SGLT2i", -1, "safety_hypotension: symptomatic/low-SBP burden, SGLT2i down"

    if (not pd.isna(cr_pct)) and float(cr_pct) >= cfg.CR_PCT_HOLD:
        if raasi > 0 or mra > 0:
            if raasi >= mra and raasi > 0:
                return "RAASi", -1, f"safety_renal: Cr_pct_ch={float(cr_pct):.1f}% >= {cfg.CR_PCT_HOLD}%, RAASi down"
            if mra > 0:
                return "MRA", -1, f"safety_renal: Cr_pct_ch={float(cr_pct):.1f}% >= {cfg.CR_PCT_HOLD}%, MRA down"

    # C) Initiate missing pillars in order
    stable_bp = _stable_bp(row, cfg)
    stable_hr = _stable_hr(row, cfg)
    cr_safe = _cr_safe(row, cfg)

    for med in ORDER:
        dose = int(row.get(med, 0))
        if dose != 0:
            continue
        if med == "RAASi" and stable_bp and k < cfg.K_HOLD and cr_safe:
            return "RAASi", +1, "initiation: missing RAASi and eligible (stable BP/K/renal trend)"
        if med == "BB" and stable_bp and stable_hr:
            return "BB", +1, "initiation: missing BB and eligible (stable BP/HR)"
        if med == "MRA" and stable_bp and gfr > cfg.GFR_MRA_MIN and k < cfg.K_MRA_INIT:
            return "MRA", +1, "initiation: missing MRA and eligible (K/GFR/BP safe)"
        if med == "SGLT2i" and stable_bp and gfr > cfg.GFR_SGLT2_MIN:
            return "SGLT2i", +1, "initiation: missing SGLT2i and eligible"

    # D) Up-titrate existing meds (SGLT2i binary, no up-titration)
    if raasi > 0 and raasi < 4 and stable_bp and k < cfg.K_HOLD and cr_safe:
        return "RAASi", +1, "uptitration: RAASi eligible and below max"
    if bb > 0 and bb < 4 and stable_bp and stable_hr:
        return "BB", +1, "uptitration: BB eligible and below max"
    if mra > 0 and mra < 4 and stable_bp and gfr > cfg.GFR_MRA_MIN and k < cfg.K_MRA_UP:
        return "MRA", +1, "uptitration: MRA eligible and below max"

    # E) No change
    return "NONE", 0, "no_change: no safety trigger and no eligible initiation/uptitration"


def add_doctor_brain_columns(df, cfg):
    out = df.copy()
    recs = out.apply(lambda r: recommend_sequence_titration(r, cfg), axis=1)
    out["Sequence"] = recs.apply(lambda x: x[0])
    out["titration"] = recs.apply(lambda x: int(x[1]))
    out["criteria"] = recs.apply(lambda x: x[2])
    return out
