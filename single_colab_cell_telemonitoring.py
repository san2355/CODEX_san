# Single Colab cell (copy/paste): Streamlit telemonitoring app + public URL (NO ngrok)
# - Uses Cloudflare Quick Tunnel via cloudflared
# - Writes app.py then runs streamlit, prints a shareable URL

import os
import re
import subprocess
import sys
import textwrap
import time

# 1) Install deps
subprocess.check_call([
    sys.executable,
    "-m",
    "pip",
    "install",
    "-q",
    "streamlit",
    "streamlit-autorefresh",
    "pandas",
    "numpy",
    "plotly",
])

# 2) Write Streamlit app
app_code = r'''
import random
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(layout="wide", page_title="Cardiology RPM Dashboard")
st.title("🫀 ICU-Style Live Cardiology RPM Dashboard (Colab Demo, no ngrok)")

st.sidebar.header("Controls")

default_patients = ["HF001", "HF002", "HF003", "HF004"]
patients_text = st.sidebar.text_area(
    "Patient IDs (comma-separated)",
    value=",".join(default_patients),
    help="Example: HF001,HF002,HF003",
)
patients = [p.strip() for p in patients_text.split(",") if p.strip()]
if not patients:
    st.warning("Add at least one patient ID in the sidebar.")
    st.stop()

refresh_seconds = st.sidebar.slider("Auto-refresh (seconds)", 5, 120, 60, 5)
simulate_on = st.sidebar.toggle("Simulate incoming vitals", value=True)
points_per_refresh = st.sidebar.slider("New readings per refresh (per patient)", 1, 5, 1)

history_hours = st.sidebar.slider("Keep history (hours)", 1, 168, 24, 1)
max_rows = st.sidebar.slider("Hard row cap (safety)", 500, 200000, 20000, 500)

if st_autorefresh is not None:
    st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh")
else:
    st.sidebar.warning("Auto-refresh unavailable: install `streamlit-autorefresh` for timed reloads.")

col1, col2 = st.sidebar.columns(2)
if col1.button("🧹 Clear data", width='stretch'):
    st.session_state.vitals_data = []
    st.session_state.last_weight = {pid: 75.0 for pid in patients}
    st.rerun()

if col2.button("📥 Seed demo", width='stretch'):
    st.session_state.vitals_data = []
    st.session_state.last_weight = {pid: 75.0 for pid in patients}
    now = datetime.now()
    for pid in patients:
        w = st.session_state.last_weight.get(pid, 75.0)
        for k in range(30):
            t = now - timedelta(minutes=(30 - k) * 10)
            w += random.uniform(-0.2, 0.3)
            st.session_state.vitals_data.append(
                {
                    "patient_id": pid,
                    "systolic": random.randint(110, 170),
                    "diastolic": random.randint(65, 100),
                    "heart_rate": random.randint(55, 115),
                    "weight": round(w, 2),
                    "spo2": random.randint(90, 100),
                    "timestamp": t,
                }
            )
    st.rerun()

if "vitals_data" not in st.session_state:
    st.session_state.vitals_data = []

if "last_weight" not in st.session_state:
    st.session_state.last_weight = {pid: 75.0 for pid in patients}
else:
    for pid in patients:
        st.session_state.last_weight.setdefault(pid, 75.0)


def generate_vitals(pids: list[str], n_per_patient: int = 1):
    now = datetime.now()
    out = []
    for pid in pids:
        w = st.session_state.last_weight.get(pid, 75.0)
        for _ in range(n_per_patient):
            w += random.uniform(-0.3, 0.5)
            st.session_state.last_weight[pid] = w

            systolic = random.randint(110, 180)
            diastolic = random.randint(70, 105)
            hr = random.randint(55, 125)
            spo2 = random.randint(90, 100)

            out.append(
                {
                    "patient_id": pid,
                    "systolic": int(systolic),
                    "diastolic": int(diastolic),
                    "heart_rate": int(hr),
                    "weight": round(float(w), 2),
                    "spo2": int(spo2),
                    "timestamp": now,
                }
            )
    return out


if simulate_on:
    st.session_state.vitals_data.extend(generate_vitals(patients, points_per_refresh))

df = pd.DataFrame(st.session_state.vitals_data)
if df.empty:
    st.info("No data yet. Turn on simulation or click **Seed demo** in the sidebar.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"]).sort_values(["patient_id", "timestamp"])

cutoff = datetime.now() - timedelta(hours=history_hours)
df = df[df["timestamp"] >= cutoff]

if len(df) > max_rows:
    df = df.sort_values("timestamp").tail(max_rows)

st.session_state.vitals_data = df.to_dict("records")


def latest_row_per_patient(dataframe: pd.DataFrame) -> pd.DataFrame:
    idx = dataframe.groupby("patient_id")["timestamp"].idxmax()
    return dataframe.loc[idx].sort_values("patient_id")


def risk_label(latest_row: pd.Series, patient_df: pd.DataFrame) -> str:
    sbp = float(latest_row["systolic"])
    hr = float(latest_row["heart_rate"])
    w_now = float(latest_row["weight"])

    target_time = latest_row["timestamp"] - timedelta(hours=24)
    patient_df = patient_df.sort_values("timestamp")
    if len(patient_df) >= 2:
        base_idx = (patient_df["timestamp"] - target_time).abs().idxmin()
        w_base = float(patient_df.loc[base_idx, "weight"])
    else:
        w_base = w_now

    w_delta = w_now - w_base

    critical = (sbp > 160) or (hr > 110) or (w_delta > 2.0)
    moderate = (sbp > 140) or (hr > 100) or (w_delta > 1.0)

    if critical:
        return "🔴 Critical"
    if moderate:
        return "🟡 Moderate"
    return "🟢 Stable"


st.subheader("🩺 Patient Wall (Latest Measurements)")
latest = latest_row_per_patient(df).copy()

risk = []
for _, row in latest.iterrows():
    pid = row["patient_id"]
    patient_hist = df[df["patient_id"] == pid]
    risk.append(risk_label(row, patient_hist))
latest["Risk"] = risk

show_cols = ["patient_id", "systolic", "diastolic", "heart_rate", "weight", "spo2", "timestamp", "Risk"]
st.dataframe(latest[show_cols], width='stretch', hide_index=True)

st.subheader("⚠️ Alerts Summary (Last 24h)")
now = datetime.now()
df_24h = df[df["timestamp"] >= (now - timedelta(hours=24))].copy()

alerts = []
for pid in patients:
    p = df_24h[df_24h["patient_id"] == pid].sort_values("timestamp")
    if p.empty:
        continue
    last = p.iloc[-1]
    label = risk_label(last, df[df["patient_id"] == pid])
    if label.startswith("🔴"):
        alerts.append(last)

if alerts:
    alerts_df = pd.DataFrame(alerts)[["patient_id", "systolic", "heart_rate", "weight", "spo2", "timestamp"]]
    st.dataframe(alerts_df.sort_values(["patient_id", "timestamp"]), width='stretch', hide_index=True)
else:
    st.success("No critical alerts in last 24h (based on current rules).")

st.subheader("📈 Patient Trend Panels")
cols = st.columns(min(len(patients), 4))
for i, pid in enumerate(patients[:4]):
    p = df[df["patient_id"] == pid].sort_values("timestamp").copy()
    if p.empty:
        continue
    with cols[i]:
        st.markdown(f"**Patient {pid}**")
        fig = px.line(p, x="timestamp", y=["systolic", "heart_rate", "weight", "spo2"], height=280)
        st.plotly_chart(fig, width='stretch')

if len(patients) > 4:
    st.markdown("### More patients")
    for pid in patients[4:]:
        p = df[df["patient_id"] == pid].sort_values("timestamp")
        if p.empty:
            continue
        fig = px.line(p, x="timestamp", y=["systolic", "heart_rate", "weight", "spo2"], height=260)
        st.plotly_chart(fig, width='stretch')

st.subheader("💊 Medication Suggestions (Simulated Rules)")
suggestions = []

for pid in patients:
    p = df[df["patient_id"] == pid].sort_values("timestamp")
    if len(p) < 2:
        continue

    last = p.iloc[-1]
    sbp = float(last["systolic"])
    hr = float(last["heart_rate"])

    if sbp > 160:
        suggestions.append(
            f"Patient {pid}: SBP > 160 → consider antihypertensive adjustment / volume assessment."
        )
    if hr > 110:
        suggestions.append(f"Patient {pid}: HR > 110 → consider rate control evaluation.")

    t0 = last["timestamp"] - timedelta(hours=24)
    base_idx = (p["timestamp"] - t0).abs().idxmin()
    w_delta = float(last["weight"]) - float(p.loc[base_idx, "weight"])
    if w_delta > 2.0:
        suggestions.append(f"Patient {pid}: Weight +{w_delta:.1f} kg vs ~24h → consider diuretic adjustment.")

if suggestions:
    for suggestion in suggestions:
        st.warning(suggestion)
else:
    st.success("No medication adjustments suggested by current demo rules.")

st.subheader("📤 Export")
csv_bytes = df.sort_values(["patient_id", "timestamp"]).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download current data as CSV",
    data=csv_bytes,
    file_name="vitals_export.csv",
    mime="text/csv",
)
'''
with open("app.py", "w", encoding="utf-8") as f:
    f.write(textwrap.dedent(app_code))

# 3) Install cloudflared (for public URL without ngrok)
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.check_call(
        [
            "wget",
            "-q",
            "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
            "-O",
            "/usr/local/bin/cloudflared",
        ]
    )
    subprocess.check_call(["chmod", "+x", "/usr/local/bin/cloudflared"])

# 4) Run Streamlit (headless) on 8501
subprocess.run(["pkill", "-f", "streamlit run app.py"], check=False)

streamlit_cmd = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    "app.py",
    "--server.port",
    "8501",
    "--server.address",
    "0.0.0.0",
    "--server.headless",
    "true",
    "--browser.gatherUsageStats",
    "false",
]
st_proc = subprocess.Popen(streamlit_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# 5) Start Cloudflare quick tunnel to Streamlit
cf_proc = subprocess.Popen(
    ["/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8501"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
)

# 6) Print the public URL
public_url = None
t0 = time.time()
pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com", re.I)

while time.time() - t0 < 30 and public_url is None:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    m = pattern.search(line)
    if m:
        public_url = m.group(0)
        break

if public_url:
    print("\n✅ Streamlit is live here (public URL):")
    print(public_url)
    print("\nTip: leave this cell running to keep the app online.")
else:
    print("\n⚠️ Could not detect the Cloudflare URL yet. Showing recent tunnel logs:\n")
    for _ in range(20):
        line = cf_proc.stdout.readline()
        if not line:
            break
        print(line.rstrip())
