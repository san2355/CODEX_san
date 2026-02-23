# Colab demo: apply Doctor Brain titration recommendations to existing `df` from simulator cell.

import importlib.util

USING_PACKAGE = importlib.util.find_spec("hfref_simulator") is not None

if USING_PACKAGE:
    from hfref_simulator.config import SimulatorConfig
    from hfref_simulator.decision_engine import add_doctor_brain_columns
else:
    # Reuse single-cell fallback implementation if package is unavailable.
    # Users can run colab_decision_single_cell.py directly in that case.
    raise ModuleNotFoundError(
        "`hfref_simulator` not found. Use `colab_decision_single_cell.py` which includes embedded fallback logic."
    )

if "df" not in globals():
    raise NameError("Expected dataframe `df` from your Visit-1 simulator cell. Please run that cell first.")

cfg = SimulatorConfig(seed=42)
df_plan = add_doctor_brain_columns(df, cfg)

cols = [
    c
    for c in [
        "Pat_ID",
        "RAASi",
        "BB",
        "MRA",
        "SGLT2i",
        "SBP",
        "HR",
        "TIR_low_sys",
        "TIR_low_HR",
        "K",
        "Cr",
        "GFR",
        "Cr_pct_ch",
        "Sequence",
        "titration",
        "criteria",
    ]
    if c in df_plan.columns
]
display_df = df_plan[cols].copy()
num_cols = display_df.select_dtypes(include=["float", "float64", "float32"]).columns
display_df[num_cols] = display_df[num_cols].round(1)
for col in ["SBP", "HR", "TIR_low_sys", "TIR_low_HR"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].round(0).astype(int)
print(display_df.head(10))
print("\nCounts by recommendation")
print(df_plan.groupby(["Sequence", "titration"]).size().sort_values(ascending=False))
