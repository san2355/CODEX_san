# Single Colab cell: apply Doctor Brain recommendations to existing Visit-1 dataframe `df`.
# Assumes you already ran simulator in another cell and have `df` in memory.
# Output: adds Sequence, titration, criteria columns.

from dataclasses import dataclass
import importlib.util
import pandas as pd


USING_PACKAGE = importlib.util.find_spec("hfref_simulator") is not None

if USING_PACKAGE:
    from hfref_simulator.config import SimulatorConfig
    from hfref_simulator.decision_engine import add_doctor_brain_columns
else:
    @dataclass
    class SimulatorConfig:
        TIR_HI: float = 10.0
        CR_PCT_HOLD: float = 50.0

    def _cr_safe(row, cfg):
        cr_pct = row.get("Cr_pct_ch")
        return pd.isna(cr_pct) or float(cr_pct) < cfg.CR_PCT_HOLD

    def _no_change_window(row):
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
        if _no_change_window(row) and sx_hypot == 0:
            return 0, "no_change_raasi_protocol"
        if cr < 3 and _cr_safe(row, cfg) and k < 5.5 and tir_sbp <= 10 and sx_hypot == 0:
            return +1, "uptitration_raasi_protocol"
        return 0, "no_change_raasi_protocol"

    def _bb_action(row):
        tir_hr = float(row.get("TIR_low_HR", 0))
        tir_sbp = float(row.get("TIR_low_sys", 0))
        sx_brady = int(row.get("Sx_brady", 0))
        sx_hypot = int(row.get("Sx_hypot", 0))
        if tir_hr > 10 or tir_sbp > 10 or sx_brady == 1 or sx_hypot == 1:
            return -1, "safety_bradycardia/bp_protocol_down: BB protocol down-titration"
        if _no_change_window(row) and sx_brady == 0 and sx_hypot == 0:
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
        if _no_change_window(row) and sx_hypot == 0:
            return 0, "no_change_mra_protocol"
        if gfr > 30 and cr < cr_cutoff and _cr_safe(row, cfg) and k < 5 and tir_sbp <= 10 and sx_hypot == 0:
            return +1, "uptitration_mra_protocol"
        return 0, "no_change_mra_protocol"

    def _sglt2_action(row):
        gfr = float(row.get("GFR", 999))
        tir_sbp = float(row.get("TIR_low_sys", 0))
        sx_hypot = int(row.get("Sx_hypot", 0))
        if gfr <= 25 or tir_sbp > 10 or sx_hypot == 1:
            return -1, "safety_sglt2i_protocol_down: SGLT2i protocol down-titration"
        if _no_change_window(row) and sx_hypot == 0:
            return 0, "no_change_sglt2i_protocol"
        if gfr > 25 and tir_sbp <= 10 and sx_hypot == 0:
            return +1, "uptitration_sglt2i_protocol"
        return 0, "no_change_sglt2i_protocol"

    def _recommend_sequence_titration(row, cfg):
        order = ["RAASi", "BB", "MRA", "SGLT2i"]
        doses = {
            "RAASi": int(row.get("RAASi", 0)),
            "BB": int(row.get("BB", 0)),
            "MRA": int(row.get("MRA", 0)),
            "SGLT2i": int(row.get("SGLT2i", 0)),
        }

        k = float(row.get("K", 0))
        tir_hr = float(row.get("TIR_low_HR", 0))
        tir_sbp = float(row.get("TIR_low_sys", 0))
        sx_brady = int(row.get("Sx_brady", 0))
        sx_hypot = int(row.get("Sx_hypot", 0))

        actions = {
            "RAASi": _raasi_action(row, cfg),
            "BB": _bb_action(row),
            "MRA": _mra_action(row, cfg),
            "SGLT2i": _sglt2_action(row),
        }

        if (sx_brady == 1 or tir_hr > 10) and doses["BB"] > 0:
            return "BB", -1, "safety_bradycardia: BB protocol down-titration"

        if k >= 5.5:
            if doses["MRA"] > 0:
                return "MRA", -1, "safety_hyperkalemia: MRA protocol down-titration"
            if doses["RAASi"] > 0:
                return "RAASi", -1, "safety_hyperkalemia: RAASi protocol down-titration"

        if sx_hypot == 1 or tir_sbp > 10:
            if doses["RAASi"] > 0:
                return "RAASi", -1, "safety_hypotension: RAASi protocol down-titration"

        for med in order:
            action, reason = actions[med]
            if doses[med] > 0 and action < 0:
                return med, -1, reason

        # Deliverable rule: if any meds are 0, initiate first in order.
        for med in order:
            if doses[med] == 0:
                return med, +1, f"initiation_priority_order: {med} is first zero-dose pillar"

        # Deliverable rule: if all meds are >=1, up-titrate first in order that is <4.
        for med in order:
            if med != "SGLT2i" and 1 <= doses[med] < 4:
                return med, +1, f"uptitration_priority_order: {med} is first submaximal pillar"

        return "NONE", 0, "protocol_no_change: no down-trigger and all pillars at max/maintained"

    def add_doctor_brain_columns(df_in, cfg):
        out = df_in.copy()
        recs = out.apply(lambda r: _recommend_sequence_titration(r, cfg), axis=1)
        out["Sequence"] = recs.apply(lambda x: x[0])
        out["titration"] = recs.apply(lambda x: int(x[1]))
        out["criteria"] = recs.apply(lambda x: x[2])
        return out


if "df" not in globals():
    raise NameError("Expected dataframe `df` from your Visit-1 simulator cell. Please run that cell first.")

cfg = SimulatorConfig()
df_plan = add_doctor_brain_columns(df, cfg)

show_cols = [
    c
    for c in [
        "Pat_ID", "Visit", "RAASi", "BB", "MRA", "SGLT2i",
        "SBP", "HR", "TIR_low_sys", "TIR_low_HR",
        "K", "Cr", "GFR", "Cr_pct_ch", "Sx_hypot", "Sx_brady",
        "Sequence", "titration", "criteria",
    ]
    if c in df_plan.columns
]

display_df = df_plan[show_cols].copy()

float_cols = display_df.select_dtypes(include=["float", "float64", "float32"]).columns
display_df[float_cols] = display_df[float_cols].round(1)

for col in ["SBP", "HR", "TIR_low_sys", "TIR_low_HR"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].round(0).astype(int)

if not USING_PACKAGE:
    print("Note: `hfref_simulator` package not found. Using embedded Doctor Brain fallback logic in this cell.")

print(display_df.head(10))
print("\nCounts by recommendation")
print(df_plan.groupby(["Sequence", "titration"]).size().sort_values(ascending=False))
