# Single Colab cell (copy/paste): Telemonitoring app with Longitudinal Patient Analysis + public URL
# Paste this whole file content in one Colab cell and run.

import os
import re
import subprocess
import sys
import textwrap
import time

# 1) Dependencies
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

# 2) Write Streamlit app (self-contained, no git clone required)
app_code = r'''
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

st.set_page_config(layout="wide", page_title="Cardiology RPM Dashboard")
st.title("🫀 ICU-Style Live Cardiology RPM Dashboard")

st.sidebar.header("Controls")
default_patients = ["HF001", "HF002", "HF003", "HF004"]
patients_text = st.sidebar.text_area("Patient IDs (comma-separated)", value=",".join(default_patients))
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

if st.sidebar.button("🧹 Clear data", use_container_width=True):
    st.session_state.vitals_data = []
    st.session_state.last_weight = {pid: 75.0 for pid in patients}
    st.rerun()

if st.sidebar.button("📥 Seed demo", use_container_width=True):
    st.session_state.vitals_data = []
    st.session_state.last_weight = {pid: 75.0 for pid in patients}
    now = datetime.now()
    for pid in patients:
        w = st.session_state.last_weight.get(pid, 75.0)
        for k in range(45):
            t = now - timedelta(minutes=(45 - k) * 20)
            w += random.uniform(-0.2, 0.3)
            st.session_state.vitals_data.append({
                "patient_id": pid,
                "systolic": random.randint(110, 175),
                "diastolic": random.randint(65, 100),
                "heart_rate": random.randint(55, 120),
                "weight": round(w, 2),
                "spo2": random.randint(90, 100),
                "timestamp": t,
            })
    st.rerun()

if "vitals_data" not in st.session_state:
    st.session_state.vitals_data = []
if "last_weight" not in st.session_state:
    st.session_state.last_weight = {pid: 75.0 for pid in patients}


def generate_vitals(pids, n_per_patient=1):
    now = datetime.now()
    out = []
    for pid in pids:
        w = st.session_state.last_weight.get(pid, 75.0)
        for _ in range(n_per_patient):
            w += random.uniform(-0.3, 0.5)
            st.session_state.last_weight[pid] = w
            out.append({
                "patient_id": pid,
                "systolic": random.randint(110, 180),
                "diastolic": random.randint(70, 105),
                "heart_rate": random.randint(55, 125),
                "weight": round(float(w), 2),
                "spo2": random.randint(90, 100),
                "timestamp": now,
            })
    return out

if simulate_on:
    st.session_state.vitals_data.extend(generate_vitals(patients, points_per_refresh))

df = pd.DataFrame(st.session_state.vitals_data)
if df.empty:
    st.info("No data yet. Turn on simulation or click Seed demo.")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
df = df.dropna(subset=["timestamp"]).sort_values(["patient_id", "timestamp"])
cutoff = datetime.now() - timedelta(hours=history_hours)
df = df[df["timestamp"] >= cutoff]
if len(df) > max_rows:
    df = df.sort_values("timestamp").tail(max_rows)

st.session_state.vitals_data = df.to_dict("records")

st.subheader("📈 Patient Trend Panels")
cols = st.columns(min(len(patients), 4))
for i, pid in enumerate(patients[:4]):
    p = df[df["patient_id"] == pid].sort_values("timestamp")
    with cols[i]:
        st.markdown(f"**Patient {pid}**")
        fig = px.line(p, x="timestamp", y=["systolic", "heart_rate", "weight", "spo2"], height=260)
        st.plotly_chart(fig, use_container_width=True)

st.subheader("🧭 Longitudinal Patient Analysis")
selected_patient = st.selectbox("Select patient for deep trend review", options=sorted(df["patient_id"].unique().tolist()))
patient_df = df[df["patient_id"] == selected_patient].sort_values("timestamp").copy()
min_ts = patient_df["timestamp"].min().to_pydatetime()
max_ts = patient_df["timestamp"].max().to_pydatetime()

c1, c2, c3, c4 = st.columns([1.1, 1.1, 0.8, 1])
with c1:
    window_mode = st.selectbox("Time window", ["All data", "Last 30 days", "Last 90 days", "Last 180 days", "Last 365 days", "Custom range"], index=0)
with c2:
    cadence = st.selectbox("X-axis cadence", ["Raw readings", "Daily", "Weekly", "Monthly"], index=2)
with c3:
    y_metric = st.selectbox("Y-axis metric", ["systolic", "heart_rate", "weight", "spo2"], index=0)
with c4:
    apply_quick_lookback = st.toggle("Limit lookback", value=False)

lookback_years = st.slider("Quick years back", 1, 5, 2, disabled=not apply_quick_lookback)
range_start, range_end = min_ts, max_ts
if window_mode == "Last 30 days": range_start = max_ts - timedelta(days=30)
elif window_mode == "Last 90 days": range_start = max_ts - timedelta(days=90)
elif window_mode == "Last 180 days": range_start = max_ts - timedelta(days=180)
elif window_mode == "Last 365 days": range_start = max_ts - timedelta(days=365)
elif window_mode == "Custom range":
    chosen = st.date_input("Choose custom date range", value=(min_ts.date(), max_ts.date()), min_value=min_ts.date(), max_value=max_ts.date())
    if isinstance(chosen, tuple) and len(chosen) == 2:
        range_start = datetime.combine(chosen[0], datetime.min.time())
        range_end = datetime.combine(chosen[1], datetime.max.time())
if apply_quick_lookback:
    range_start = max(range_start, max_ts - timedelta(days=365 * lookback_years))

filtered = patient_df[(patient_df["timestamp"] >= range_start) & (patient_df["timestamp"] <= range_end)].copy()
if filtered.empty:
    st.warning("No readings for the selected patient in that time range.")
    st.stop()

freq_map = {"Raw readings": None, "Daily": "D", "Weekly": "W", "Monthly": "ME"}
freq = freq_map[cadence]
if freq is None:
    trend = filtered[["timestamp", y_metric]].rename(columns={"timestamp": "period", y_metric: "median"})
    trend["p05"] = trend["median"]
    trend["p25"] = trend["median"]
    trend["p75"] = trend["median"]
    trend["p95"] = trend["median"]
else:
    trend = (
        filtered.set_index("timestamp")[y_metric]
        .resample(freq)
        .agg(
            p05=lambda x: np.nanpercentile(x, 5),
            p25=lambda x: np.nanpercentile(x, 25),
            median="median",
            p75=lambda x: np.nanpercentile(x, 75),
            p95=lambda x: np.nanpercentile(x, 95),
        )
        .dropna(subset=["median"])
        .reset_index(names="period")
    )

def sbp_zone(v):
    if v <= 79: return "Very Low"
    if v <= 89: return "Low"
    if v <= 140: return "Target"
    if v <= 160: return "High"
    return "Very High"

sbp_scope = filtered[["timestamp", "systolic"]].copy()
sbp_scope["period"] = sbp_scope["timestamp"].dt.to_period("M").astype(str)
period_counts = sbp_scope.groupby("period")["systolic"].count().sort_index()
eligible = period_counts[period_counts >= 10]
report_period = eligible.index.max() if not eligible.empty else period_counts.index.max()
report_df = sbp_scope[sbp_scope["period"] == report_period].copy()
report_df["zone"] = report_df["systolic"].apply(sbp_zone)
zone_order = ["Very High", "High", "Target", "Low", "Very Low"]
zone_pct = report_df["zone"].value_counts(normalize=True).reindex(zone_order).fillna(0) * 100

fig = make_subplots(rows=1, cols=2, column_widths=[0.32, 0.68], subplot_titles=(f"SBP Time in Range — {report_period}", f"{y_metric.replace('_', ' ').title()} longitudinal profile"))
colors = {"Very Low": "#313695", "Low": "#74add1", "Target": "#66bd63", "High": "#fdae61", "Very High": "#d73027"}
for z in zone_order[::-1]:
    fig.add_trace(go.Bar(x=[report_period], y=[float(zone_pct[z])], name=z, marker_color=colors[z]), row=1, col=1)

fig.add_trace(go.Scatter(x=trend["period"], y=trend["p95"], mode="lines", line=dict(width=0), showlegend=False), row=1, col=2)
fig.add_trace(go.Scatter(x=trend["period"], y=trend["p05"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(99,110,250,0.18)", name="5-95%"), row=1, col=2)
fig.add_trace(go.Scatter(x=trend["period"], y=trend["p75"], mode="lines", line=dict(width=0), showlegend=False), row=1, col=2)
fig.add_trace(go.Scatter(x=trend["period"], y=trend["p25"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(99,110,250,0.35)", name="25-75%"), row=1, col=2)
fig.add_trace(go.Scatter(x=trend["period"], y=trend["median"], mode="lines+markers", line=dict(color="#1f3c88", width=2.5), name="Median"), row=1, col=2)

if y_metric == "systolic":
    fig.add_hrect(y0=90, y1=140, line_width=0, fillcolor="rgba(102,189,99,0.14)", row=1, col=2)

fig.update_layout(barmode="stack", height=560, title=f"Patient {selected_patient} • {window_mode} • {cadence} cadence")
fig.update_yaxes(title_text="Percent of readings (%)", range=[0, 100], row=1, col=1)
fig.update_yaxes(title_text=y_metric.replace("_", " ").title(), row=1, col=2)
st.plotly_chart(fig, use_container_width=True)
'''

with open("app.py", "w", encoding="utf-8") as f:
    f.write(textwrap.dedent(app_code))

# 3) Install cloudflared
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.check_call([
        "wget",
        "-q",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64",
        "-O",
        "/usr/local/bin/cloudflared",
    ])
    subprocess.check_call(["chmod", "+x", "/usr/local/bin/cloudflared"])

# 4) Launch streamlit
subprocess.run(["pkill", "-f", "streamlit run app.py"], check=False)
subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", "app.py",
    "--server.port", "8501",
    "--server.address", "0.0.0.0",
    "--server.headless", "true",
    "--browser.gatherUsageStats", "false",
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# 5) Cloudflare tunnel and URL
cf_proc = subprocess.Popen([
    "/usr/local/bin/cloudflared", "tunnel", "--url", "http://localhost:8501"
], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

public_url = None
pattern = re.compile(r"https://[a-z0-9\-]+\.trycloudflare\.com", re.I)
start = time.time()
while time.time() - start < 45 and public_url is None:
    line = cf_proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    m = pattern.search(line)
    if m:
        public_url = m.group(0)

if public_url:
    print("\n✅ App live URL:")
    print(public_url)
    print("\nScroll to section: 🧭 Longitudinal Patient Analysis")
else:
    print("\n⚠️ Could not detect tunnel URL yet.")
