"""Run a local telemonitoring demo without ngrok.

This script starts:
1) FastAPI backend on http://127.0.0.1:8000
2) Background patient simulator posting vitals every 3s
3) Streamlit dashboard on http://127.0.0.1:8501

Usage:
    pip install fastapi "uvicorn[standard]" streamlit pandas plotly requests
    python telemonitoring_streamlit_local.py
"""

from __future__ import annotations

import random
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

PATIENT_IDS = ["HF001", "HF002", "HF003", "HF004"]
LAST_WEIGHT = {pid: 75.0 for pid in PATIENT_IDS}
ROOT = Path(__file__).resolve().parent


API_CODE = """
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Telemonitoring API")
database = []


class Vital(BaseModel):
    patient_id: str
    systolic: int
    diastolic: int
    heart_rate: int
    weight: float
    spo2: int
    timestamp: datetime


@app.post("/vitals")
def receive_vitals(v: Vital):
    database.append(v.dict())
    return {"status": "ok"}


@app.get("/vitals")
def get_vitals():
    return database
""".strip() + "\n"


STREAMLIT_CODE = """
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(layout="wide")
st.title("🫀 ICU-Style Live Cardiology RPM Dashboard")

API_BASE = st.sidebar.text_input("API URL", "http://127.0.0.1:8000")
auto_refresh = st.sidebar.slider("Auto-refresh (seconds)", 3, 60, 10)
st.caption("Tip: keep this app local; ngrok is not required.")


@st.cache_data(ttl=1)
def fetch_vitals(api_base: str):
    response = requests.get(f"{api_base}/vitals", timeout=5)
    response.raise_for_status()
    return response.json()


placeholder = st.empty()

try:
    rows = fetch_vitals(API_BASE)
except Exception as exc:
    st.error(f"Cannot fetch data from {API_BASE}: {exc}")
    st.stop()

if not rows:
    st.info("Waiting for incoming vitals…")
    st.stop()


df = pd.DataFrame(rows)
df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp")

st.subheader("🩺 Patient Wall (Latest Measurements)")
latest = df.groupby("patient_id", as_index=False).tail(1).copy()


# lightweight risk tagging
latest["Risk"] = np.select(
    [
        (latest["systolic"] > 160) | (latest["heart_rate"] > 110) | (latest["spo2"] < 92),
        (latest["systolic"] > 140) | (latest["heart_rate"] > 100) | (latest["spo2"] < 95),
    ],
    ["🔴 Critical", "🟡 Moderate"],
    default="🟢 Stable",
)
st.dataframe(
    latest[["patient_id", "systolic", "diastolic", "heart_rate", "weight", "spo2", "Risk"]],
    use_container_width=True,
)

st.subheader("⚠️ Alerts Summary (Last 24h)")
now = datetime.now()
recent_alerts = df[
    (df["systolic"] > 160)
    | (df["heart_rate"] > 110)
    | (df["spo2"] < 92)
    | (df["timestamp"] > now - timedelta(hours=24))
]
if len(recent_alerts):
    st.dataframe(
        recent_alerts[["patient_id", "systolic", "heart_rate", "spo2", "weight", "timestamp"]],
        use_container_width=True,
    )
else:
    st.success("No critical alerts in last 24h")

st.subheader("📈 Patient Trend Panels")
for pid in sorted(df["patient_id"].unique()):
    patient = df[df["patient_id"] == pid].copy()
    st.markdown(f"**Patient {pid}**")
    fig = px.line(
        patient,
        x="timestamp",
        y=["systolic", "heart_rate", "weight", "spo2"],
        height=260,
    )
    st.plotly_chart(fig, use_container_width=True)



st.subheader("🧭 Longitudinal Patient Analysis")
selected_patient = st.selectbox(
    "Select patient for deep trend review",
    options=sorted(df["patient_id"].unique().tolist()),
)

patient_df = df[df["patient_id"] == selected_patient].sort_values("timestamp").copy()
min_ts = patient_df["timestamp"].min().to_pydatetime()
max_ts = patient_df["timestamp"].max().to_pydatetime()

analysis_cols = st.columns([1.1, 1.1, 0.8, 1])
with analysis_cols[0]:
    window_mode = st.selectbox(
        "Time window",
        ["All data", "Last 30 days", "Last 90 days", "Last 180 days", "Last 365 days", "Custom range"],
        index=0,
    )
with analysis_cols[1]:
    cadence = st.selectbox("X-axis cadence", ["Raw readings", "Daily", "Weekly", "Monthly"], index=2)
with analysis_cols[2]:
    y_metric = st.selectbox("Y-axis metric", ["systolic", "heart_rate", "weight", "spo2"], index=0)
with analysis_cols[3]:
    apply_quick_lookback = st.toggle("Limit lookback", value=False)

lookback_years = st.slider("Quick years back", min_value=1, max_value=5, value=2, disabled=not apply_quick_lookback)

range_start, range_end = min_ts, max_ts
if window_mode == "Last 30 days":
    range_start = max_ts - timedelta(days=30)
elif window_mode == "Last 90 days":
    range_start = max_ts - timedelta(days=90)
elif window_mode == "Last 180 days":
    range_start = max_ts - timedelta(days=180)
elif window_mode == "Last 365 days":
    range_start = max_ts - timedelta(days=365)
elif window_mode == "Custom range":
    chosen = st.date_input(
        "Choose custom date range",
        value=(min_ts.date(), max_ts.date()),
        min_value=min_ts.date(),
        max_value=max_ts.date(),
    )
    if isinstance(chosen, tuple) and len(chosen) == 2:
        range_start = datetime.combine(chosen[0], datetime.min.time())
        range_end = datetime.combine(chosen[1], datetime.max.time())

if apply_quick_lookback:
    range_start = max(range_start, max_ts - timedelta(days=365 * lookback_years))

filtered_patient = patient_df[(patient_df["timestamp"] >= range_start) & (patient_df["timestamp"] <= range_end)].copy()

if filtered_patient.empty:
    st.warning("No readings for the selected patient in that time range.")
else:
    freq_map = {"Raw readings": None, "Daily": "D", "Weekly": "W", "Monthly": "ME"}
    freq = freq_map[cadence]

    if freq is None:
        trend = filtered_patient[["timestamp", y_metric]].copy()
        trend = trend.rename(columns={"timestamp": "period", y_metric: "median"})
        trend["p05"] = trend["median"]
        trend["p25"] = trend["median"]
        trend["p75"] = trend["median"]
        trend["p95"] = trend["median"]
    else:
        trend = (
            filtered_patient.set_index("timestamp")[y_metric]
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

    def sbp_zone(value: float) -> str:
        if value <= 79:
            return "Very Low"
        if value <= 89:
            return "Low"
        if value <= 140:
            return "Target"
        if value <= 160:
            return "High"
        return "Very High"

    sbp_scope = filtered_patient[["timestamp", "systolic"]].copy()
    sbp_scope["period"] = sbp_scope["timestamp"].dt.to_period("M").astype(str)
    period_counts = sbp_scope.groupby("period")["systolic"].count().sort_index()
    eligible_periods = period_counts[period_counts >= 10]
    report_period = eligible_periods.index.max() if not eligible_periods.empty else period_counts.index.max()
    report_df = sbp_scope[sbp_scope["period"] == report_period].copy()
    report_df["zone"] = report_df["systolic"].apply(sbp_zone)
    zone_order = ["Very High", "High", "Target", "Low", "Very Low"]
    zone_pct = report_df["zone"].value_counts(normalize=True).reindex(zone_order).fillna(0) * 100

    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.32, 0.68],
        subplot_titles=(
            f"SBP Time in Range — {report_period}",
            f"{y_metric.replace('_', ' ').title()} longitudinal profile",
        ),
    )

    colors = {
        "Very Low": "#313695",
        "Low": "#74add1",
        "Target": "#66bd63",
        "High": "#fdae61",
        "Very High": "#d73027",
    }
    for zone in zone_order[::-1]:
        fig.add_trace(go.Bar(x=[report_period], y=[float(zone_pct[zone])], name=zone, marker_color=colors[zone]), row=1, col=1)

    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p95"], mode="lines", line=dict(width=0), showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p05"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(99,110,250,0.18)", name="5-95%"), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p75"], mode="lines", line=dict(width=0), showlegend=False), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p25"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(99,110,250,0.35)", name="25-75%"), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["median"], mode="lines+markers", name="Median"), row=1, col=2)

    if y_metric == "systolic":
        fig.add_hrect(y0=90, y1=140, line_width=0, fillcolor="rgba(102,189,99,0.14)", row=1, col=2)

    fig.update_layout(barmode="stack", height=560, title=f"Patient {selected_patient} • {window_mode} • {cadence} cadence")
    fig.update_yaxes(title_text="Percent of readings (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text=y_metric.replace("_", " ").title(), row=1, col=2)
    st.plotly_chart(fig, use_container_width=True)

st.subheader("💊 Medication Suggestions (Simulated)")
suggestions = []
for pid in sorted(df["patient_id"].unique()):
    patient = df[df["patient_id"] == pid].tail(2)
    if len(patient) < 2:
        continue
    if (patient["weight"].iloc[-1] - patient["weight"].iloc[-2]) > 2:
        suggestions.append(f"Patient {pid}: Consider diuretic adjustment")
    if patient["systolic"].iloc[-1] > 160:
        suggestions.append(f"Patient {pid}: Consider antihypertensive adjustment")
if suggestions:
    for text in suggestions:
        st.warning(text)
else:
    st.success("No medication adjustments needed")

st.caption(f"Auto-refresh your browser every ~{auto_refresh}s.")
""".strip() + "\n"


def write_runtime_files() -> None:
    (ROOT / "telemonitor_api.py").write_text(API_CODE, encoding="utf-8")
    (ROOT / "telemonitor_app.py").write_text(STREAMLIT_CODE, encoding="utf-8")


def run_api() -> subprocess.Popen:
    return subprocess.Popen(
        [
            "uvicorn",
            "telemonitor_api:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=ROOT,
    )


def simulate_patients() -> None:
    while True:
        for pid in PATIENT_IDS:
            LAST_WEIGHT[pid] += random.uniform(-0.3, 0.5)
            payload = {
                "patient_id": pid,
                "systolic": random.randint(110, 180),
                "diastolic": random.randint(70, 100),
                "heart_rate": random.randint(60, 120),
                "weight": round(LAST_WEIGHT[pid], 2),
                "spo2": random.randint(90, 100),
                "timestamp": datetime.now().isoformat(),
            }
            try:
                requests.post("http://127.0.0.1:8000/vitals", json=payload, timeout=3)
            except requests.RequestException:
                pass
        time.sleep(3)


def run_streamlit() -> subprocess.Popen:
    return subprocess.Popen(["streamlit", "run", "telemonitor_app.py", "--server.port", "8501"], cwd=ROOT)


def main() -> None:
    write_runtime_files()
    api_proc = run_api()
    time.sleep(2)

    thread = threading.Thread(target=simulate_patients, daemon=True)
    thread.start()

    print("🚀 API URL: http://127.0.0.1:8000")
    print("🖥️ Dashboard URL: http://127.0.0.1:8501")
    print("Press Ctrl+C to stop.")

    ui_proc = run_streamlit()
    try:
        ui_proc.wait()
    except KeyboardInterrupt:
        pass
    finally:
        ui_proc.terminate()
        api_proc.terminate()


if __name__ == "__main__":
    main()
