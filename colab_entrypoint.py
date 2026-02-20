# Colab quick entrypoint.
# If you want a single copy/paste cell with no file/module dependencies,
# use `colab_single_file_simulator.py` instead.

from hfref_simulator.config import SimulatorConfig
from hfref_simulator.simulate_visit1 import calibration_report, simulate_visit1

cfg = SimulatorConfig(seed=42)
df, home_df = simulate_visit1(n_patients=10, cfg=cfg, save_csv=True)

print(df.head())
print("\nSummary stats")
print("Mean SBP:", round(df["SBP"].mean(), 1))
print("Mean HR:", round(df["HR"].mean(), 1))
print("% on RAASi:", round((df["RAASi"] > 0).mean() * 100, 1))
print("% on BB:", round((df["BB"] > 0).mean() * 100, 1))
print("% on MRA:", round((df["MRA"] > 0).mean() * 100, 1))
print("% on SGLT2i:", round((df["SGLT2i"] > 0).mean() * 100, 1))
print("% K > 5.5:", round((df["K"] > 5.5).mean() * 100, 1))
print("% Sx_hypot:", round(df["Sx_hypot"].mean() * 100, 1))

print("\nCalibration N=500")
print(calibration_report(n_patients=500, cfg=cfg))
