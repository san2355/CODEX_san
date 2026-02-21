# Single Colab cell: apply Doctor Brain recommendations to existing Visit-1 dataframe `df`.
# Assumes you already ran simulator in another cell and have `df` in memory.
# Output: adds Sequence, titration, criteria columns.

from dataclasses import dataclass
import pandas as pd


@dataclass
class DecisionConfig:
    TIR_HI: float = 10.0
    K_HOLD: float = 5.5
    K_MRA_INIT: float = 5.0
    K_MRA_UP: float = 5.0
    GFR_MRA_MIN: float = 30.0
    GFR_SGLT2_MIN: float = 25.0
    CR_PCT_HOLD: float = 50.0


def _stable_bp(row, cfg):
    return int(row.get("Sx_hypot", 0)) == 0 and float(row.get("TIR_low_sys", 0)) <= cfg.TIR_HI


def _stable_hr(row, cfg):
    return int(row.get("Sx_brady", 0)) == 0 and float(row.get("TIR_low_HR", 0)) <= cfg.TIR_HI


def _cr_safe(row, cfg):
    cr_pct = row.get("Cr_pct_ch")
    return pd.isna(cr_pct) or float(cr_pct) < cfg.CR_PCT_HOLD


def recommend_sequence_titration(row, cfg):
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

    stable_bp = _stable_bp(row, cfg)
    stable_hr = _stable_hr(row, cfg)
    cr_safe = _cr_safe(row, cfg)

    if raasi == 0 and stable_bp and k < cfg.K_HOLD and cr_safe:
        return "RAASi", +1, "initiation: missing RAASi and eligible (stable BP/K/renal trend)"
    if bb == 0 and stable_bp and stable_hr:
        return "BB", +1, "initiation: missing BB and eligible (stable BP/HR)"
    if mra == 0 and stable_bp and gfr > cfg.GFR_MRA_MIN and k < cfg.K_MRA_INIT:
        return "MRA", +1, "initiation: missing MRA and eligible (K/GFR/BP safe)"
    if sglt2 == 0 and stable_bp and gfr > cfg.GFR_SGLT2_MIN:
        return "SGLT2i", +1, "initiation: missing SGLT2i and eligible"

    if raasi > 0 and raasi < 4 and stable_bp and k < cfg.K_HOLD and cr_safe:
        return "RAASi", +1, "uptitration: RAASi eligible and below max"
    if bb > 0 and bb < 4 and stable_bp and stable_hr:
        return "BB", +1, "uptitration: BB eligible and below max"
    if mra > 0 and mra < 4 and stable_bp and gfr > cfg.GFR_MRA_MIN and k < cfg.K_MRA_UP:
        return "MRA", +1, "uptitration: MRA eligible and below max"

    return "NONE", 0, "no_change: no safety trigger and no eligible initiation/uptitration"


def add_doctor_brain_columns(df_in, cfg):
    out = df_in.copy()
    recs = out.apply(lambda r: recommend_sequence_titration(r, cfg), axis=1)
    out["Sequence"] = recs.apply(lambda x: x[0])
    out["titration"] = recs.apply(lambda x: int(x[1]))
    out["criteria"] = recs.apply(lambda x: x[2])
    return out


if "df" not in globals():
    raise NameError("Expected dataframe `df` from your Visit-1 simulator cell. Please run that cell first.")

cfg = DecisionConfig()
df_plan = add_doctor_brain_columns(df, cfg)

show_cols = [
    c
    for c in [
        "Pat_ID", "Visit", "RAASi", "BB", "MRA", "SGLT2i",
        "K", "Cr", "GFR", "Cr_pct_ch", "Sx_hypot", "Sx_brady",
        "Sequence", "titration", "criteria",
    ]
    if c in df_plan.columns
]

display_df = df_plan[show_cols].copy()
num_cols = display_df.select_dtypes(include=["float", "float64", "float32"]).columns
display_df[num_cols] = display_df[num_cols].round(1)
print(display_df.head(10))
print("\nCounts by recommendation")
print(df_plan.groupby(["Sequence", "titration"]).size().sort_values(ascending=False))
