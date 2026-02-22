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
import requests
import streamlit as st

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
