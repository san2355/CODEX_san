"""Streamlit Cloud-ready telemonitoring app (no ngrok, no FastAPI sidecar).

Deploy on Streamlit Community Cloud:
- Repo file: telemonitoring_streamlit_local.py
- App command (implicit): streamlit run telemonitoring_streamlit_local.py

This app keeps all state in Streamlit session_state and simulates incoming
multi-patient vitals on each auto-refresh cycle.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide", page_title="ICU-Style Cardiology RPM Dashboard")
st.title("🫀 ICU-Style Live Cardiology RPM Dashboard")
st.caption("Streamlit Community Cloud compatible (no ngrok, no backend process).")

# ---------------------------
# Controls
# ---------------------------
patient_ids = ["HF001", "HF002", "HF003", "HF004"]
refresh_sec = st.sidebar.slider("Auto-refresh (seconds)", min_value=5, max_value=120, value=30, step=5)
max_points = st.sidebar.slider("Max data points per patient", min_value=30, max_value=1000, value=200, step=10)

# Optional dependency fallback: works without streamlit-autorefresh package.
try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(interval=refresh_sec * 1000, key="rpm_refresh")
except Exception:
    st.sidebar.info("Install `streamlit-autorefresh` for automatic refresh on cloud.")

# ---------------------------
# State initialization
# ---------------------------
if "vitals_data" not in st.session_state:
    st.session_state.vitals_data = []

if "last_weight" not in st.session_state:
    st.session_state.last_weight = {pid: 75.0 for pid in patient_ids}


# ---------------------------
# Data generation
# ---------------------------
def generate_vitals() -> None:
    now = datetime.now()
    for pid in patient_ids:
        st.session_state.last_weight[pid] += random.uniform(-0.3, 0.5)
        st.session_state.vitals_data.append(
            {
                "patient_id": pid,
                "systolic": random.randint(110, 180),
                "diastolic": random.randint(70, 100),
                "heart_rate": random.randint(60, 120),
                "weight": round(st.session_state.last_weight[pid], 2),
                "spo2": random.randint(90, 100),
                "timestamp": now,
            }
        )

    # Bound memory per patient for cloud sessions
    df = pd.DataFrame(st.session_state.vitals_data)
    if not df.empty:
        trimmed = []
        for pid in patient_ids:
            trimmed.extend(df[df["patient_id"] == pid].tail(max_points).to_dict("records"))
        st.session_state.vitals_data = trimmed


if st.button("Generate Now"):
    generate_vitals()

# Also generate one batch every run (refresh-driven live feed).
generate_vitals()


df = pd.DataFrame(st.session_state.vitals_data)
if df.empty:
    st.info("Waiting for data...")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp")

# ---------------------------
# Patient wall
# ---------------------------
st.subheader("🩺 Patient Wall (Latest Measurements)")
latest = df.groupby("patient_id", as_index=False).tail(1).copy()

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

# ---------------------------
# Alerts
# ---------------------------
st.subheader("⚠️ Alerts Summary (Last 24h)")
now = datetime.now()
recent = df[df["timestamp"] > now - timedelta(hours=24)]
recent_alerts = recent[
    (recent["systolic"] > 160) | (recent["heart_rate"] > 110) | (recent["spo2"] < 92)
]

if recent_alerts.empty:
    st.success("No critical alerts in the last 24h")
else:
    st.dataframe(
        recent_alerts[["patient_id", "systolic", "heart_rate", "spo2", "weight", "timestamp"]],
        use_container_width=True,
    )

# ---------------------------
# Trends
# ---------------------------
st.subheader("📈 Patient Trend Panels")
cols = st.columns(len(patient_ids))
for i, pid in enumerate(patient_ids):
    patient = df[df["patient_id"] == pid].copy()
    with cols[i]:
        st.markdown(f"**Patient {pid}**")
        fig = px.line(patient, x="timestamp", y=["systolic", "heart_rate", "weight", "spo2"], height=260)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------
# Medication suggestions
# ---------------------------
st.subheader("💊 Medication Suggestions (Simulated)")
suggestions = []
for pid in patient_ids:
    patient = df[df["patient_id"] == pid].tail(2)
    if len(patient) < 2:
        continue

    if (patient["weight"].iloc[-1] - patient["weight"].iloc[-2]) > 2:
        suggestions.append(f"Patient {pid}: Consider diuretic adjustment")
    if patient["systolic"].iloc[-1] > 160:
        suggestions.append(f"Patient {pid}: Consider antihypertensive adjustment")

if suggestions:
    for item in suggestions:
        st.warning(item)
else:
    st.success("No medication adjustments needed")

st.caption(
    "Deploy tip: in Streamlit Cloud, point app entrypoint to `telemonitoring_streamlit_local.py` "
    "and include `streamlit-autorefresh` in requirements for timer refresh."
)
