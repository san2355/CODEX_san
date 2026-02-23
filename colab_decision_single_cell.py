# Single Colab cell: apply Doctor Brain recommendations to existing Visit-1 dataframe `df`.
# Assumes you already ran simulator in another cell and have `df` in memory.
# Output: adds Sequence, titration, criteria columns.

import pandas as pd

from hfref_simulator.config import SimulatorConfig
from hfref_simulator.decision_engine import add_doctor_brain_columns


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

print(display_df.head(10))
print("\nCounts by recommendation")
print(df_plan.groupby(["Sequence", "titration"]).size().sort_values(ascending=False))
