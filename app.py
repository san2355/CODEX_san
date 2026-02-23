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
st.title("Cardiology Remote Patient Monitoring Dashboard")
st.caption("Clinical Operations Workspace • Longitudinal Trend Intelligence")

st.markdown("""
<style>
:root {
  --emr-bg: #eef2f7;
  --emr-panel: #f8fafd;
  --emr-border: #c7d3e3;
  --emr-text: #1e2f4d;
}
.stApp { background-color: var(--emr-bg); color: var(--emr-text); }
section[data-testid="stSidebar"] { background: #e6edf6; border-right: 1px solid var(--emr-border); }
.block-container { padding-top: 1.2rem; }
div[data-testid="stDataFrame"] { border: 1px solid var(--emr-border); border-radius: 6px; background: var(--emr-panel); }
div[data-testid="stMetric"] { background: var(--emr-panel); border: 1px solid var(--emr-border); border-radius: 6px; padding: 0.25rem 0.5rem; }
.stAlert { border-radius: 6px; border: 1px solid var(--emr-border); }
</style>
""", unsafe_allow_html=True)

st.sidebar.header("Clinical Controls")

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
if col1.button("Clear data", width='stretch'):
    st.session_state.vitals_data = []
    st.session_state.last_weight = {pid: 75.0 for pid in patients}
    st.rerun()

if col2.button("Seed demo", width='stretch'):
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
        return "Critical"
    if moderate:
        return "Moderate"
    return "Stable"


st.subheader("Patient Wall (Latest Measurements)")
latest = latest_row_per_patient(df).copy()

risk = []
for _, row in latest.iterrows():
    pid = row["patient_id"]
    patient_hist = df[df["patient_id"] == pid]
    risk.append(risk_label(row, patient_hist))
latest["Risk"] = risk

show_cols = ["patient_id", "systolic", "diastolic", "heart_rate", "weight", "spo2", "timestamp", "Risk"]
st.dataframe(latest[show_cols], width='stretch', hide_index=True)

st.subheader("Alerts Summary (Last 24h)")
now = datetime.now()
df_24h = df[df["timestamp"] >= (now - timedelta(hours=24))].copy()

alerts = []
for pid in patients:
    p = df_24h[df_24h["patient_id"] == pid].sort_values("timestamp")
    if p.empty:
        continue
    last = p.iloc[-1]
    label = risk_label(last, df[df["patient_id"] == pid])
    if label.startswith("Critical"):
        alerts.append(last)

if alerts:
    alerts_df = pd.DataFrame(alerts)[["patient_id", "systolic", "heart_rate", "weight", "spo2", "timestamp"]]
    st.dataframe(alerts_df.sort_values(["patient_id", "timestamp"]), width='stretch', hide_index=True)
else:
    st.success("No critical alerts in last 24h (based on current rules).")

st.subheader("Patient Trend Panels (Operational View)")
cols = st.columns(min(len(patients), 4))
for i, pid in enumerate(patients[:4]):
    p = df[df["patient_id"] == pid].sort_values("timestamp").copy()
    if p.empty:
        continue
    with cols[i]:
        st.markdown(f"**Patient {pid}**")
        fig = px.line(p, x="timestamp", y=["systolic", "heart_rate", "weight", "spo2"], height=280)
        fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="#f8fafd")
        st.plotly_chart(fig, width='stretch')

if len(patients) > 4:
    st.markdown("### More patients")
    for pid in patients[4:]:
        p = df[df["patient_id"] == pid].sort_values("timestamp")
        if p.empty:
            continue
        fig = px.line(p, x="timestamp", y=["systolic", "heart_rate", "weight", "spo2"], height=260)
        fig.update_layout(template="plotly_white", margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="#f8fafd")
        st.plotly_chart(fig, width='stretch')

st.markdown(
    """
    <style>
    .emr-banner {
        background: linear-gradient(90deg, #f3f6fb 0%, #e7edf7 100%);
        border: 1px solid #c8d4e6;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.9rem;
    }
    .emr-banner h3 {
        margin: 0;
        color: #1f365c;
        font-size: 1.18rem;
    }
    .emr-banner p {
        margin: 0.25rem 0 0 0;
        color: #334e74;
        font-size: 0.9rem;
    }
    .emr-chip {
        background: #f8fafd;
        border: 1px solid #d0dbea;
        border-radius: 6px;
        padding: 0.55rem 0.75rem;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='emr-banner'>
      <h3>Longitudinal Patient Data View</h3>
      <p>AGP-style profile with configurable cadence, target lines, and period-specific time-in-range reporting.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_patient = st.selectbox(
    "Patient",
    options=sorted(df["patient_id"].unique().tolist()),
)

patient_df = df[df["patient_id"] == selected_patient].sort_values("timestamp").copy()
min_ts = patient_df["timestamp"].min().to_pydatetime()
max_ts = patient_df["timestamp"].max().to_pydatetime()

controls = st.columns([1, 1, 1, 1])
with controls[0]:
    vital = st.selectbox("Vital", ["systolic", "diastolic", "heart_rate"], index=0)
with controls[1]:
    window_mode = st.selectbox("Window", ["All data", "Last 24h", "Last 7 days", "Last 30 days", "Last 90 days", "Last 180 days", "Last 365 days", "Custom range"], index=3)
with controls[2]:
    cadence = st.selectbox("Cadence", ["Minute", "15-Minute", "Hourly", "Daily", "Weekly", "Monthly"], index=4)
with controls[3]:
    tir_period = st.selectbox("Time-in-range period", ["Day", "Week", "Month", "Custom"], index=2)

range_start, range_end = min_ts, max_ts
if window_mode == "Last 24h":
    range_start = max_ts - timedelta(hours=24)
elif window_mode == "Last 7 days":
    range_start = max_ts - timedelta(days=7)
elif window_mode == "Last 30 days":
    range_start = max_ts - timedelta(days=30)
elif window_mode == "Last 90 days":
    range_start = max_ts - timedelta(days=90)
elif window_mode == "Last 180 days":
    range_start = max_ts - timedelta(days=180)
elif window_mode == "Last 365 days":
    range_start = max_ts - timedelta(days=365)
elif window_mode == "Custom range":
    chosen = st.date_input(
        "Custom date range",
        value=(min_ts.date(), max_ts.date()),
        min_value=min_ts.date(),
        max_value=max_ts.date(),
    )
    if isinstance(chosen, tuple) and len(chosen) == 2:
        range_start = datetime.combine(chosen[0], datetime.min.time())
        range_end = datetime.combine(chosen[1], datetime.max.time())

filtered = patient_df[(patient_df["timestamp"] >= range_start) & (patient_df["timestamp"] <= range_end)].copy()

if filtered.empty:
    st.warning("No readings are available for the selected filters.")
else:
    metric_cfg = {
        "systolic": {"unit": "mmHg", "target": (90, 120), "zones": {"Very Low": (-1e9, 79), "Low": (80, 89), "Target": (90, 120), "High": (121, 140), "Very High": (141, 1e9)}},
        "diastolic": {"unit": "mmHg", "target": (60, 90), "zones": {"Very Low": (-1e9, 49), "Low": (50, 59), "Target": (60, 90), "High": (91, 100), "Very High": (101, 1e9)}},
        "heart_rate": {"unit": "bpm", "target": (60, 100), "zones": {"Very Low": (-1e9, 49), "Low": (50, 59), "Target": (60, 100), "High": (101, 120), "Very High": (121, 1e9)}},
    }
    cfg = metric_cfg[vital]

    def bucket(v: float) -> str:
        for label, (low, high) in cfg["zones"].items():
            if low <= v <= high:
                return label
        return "Very High"

    cadence_map = {"Minute": "min", "15-Minute": "15min", "Hourly": "H", "Daily": "D", "Weekly": "W", "Monthly": "ME"}
    freq = cadence_map[cadence]

    trend = (
        filtered.set_index("timestamp")[vital]
        .resample(freq)
        .agg(
            p05=lambda x: np.nanpercentile(x, 5),
            p25=lambda x: np.nanpercentile(x, 25),
            p50=lambda x: np.nanpercentile(x, 50),
            p75=lambda x: np.nanpercentile(x, 75),
            p95=lambda x: np.nanpercentile(x, 95),
        )
        .dropna()
        .reset_index(names="period")
    )

    if tir_period == "Day":
        tir_key = filtered["timestamp"].dt.to_period("D").astype(str)
    elif tir_period == "Week":
        tir_key = filtered["timestamp"].dt.to_period("W").astype(str)
    elif tir_period == "Month":
        tir_key = filtered["timestamp"].dt.to_period("M").astype(str)
    else:
        custom = st.date_input("Custom TIR period", value=(range_start.date(), range_end.date()), min_value=min_ts.date(), max_value=max_ts.date(), key="tir_custom")
        c0, c1 = range_start, range_end
        if isinstance(custom, tuple) and len(custom) == 2:
            c0 = datetime.combine(custom[0], datetime.min.time())
            c1 = datetime.combine(custom[1], datetime.max.time())
        custom_df = filtered[(filtered["timestamp"] >= c0) & (filtered["timestamp"] <= c1)].copy()
        custom_df["period"] = f"{c0.date()} to {c1.date()}"
        period_df = custom_df
        tir_key = None

    if tir_period != "Custom":
        period_df = filtered.copy()
        period_df["period"] = tir_key
        counts = period_df.groupby("period")[vital].count().sort_index()
        eligible = counts[counts >= 10]
        report_period = eligible.index.max() if not eligible.empty else counts.index.max()
        period_df = period_df[period_df["period"] == report_period].copy()
    else:
        report_period = period_df["period"].iloc[0] if not period_df.empty else "Custom"

    period_df["zone"] = period_df[vital].apply(lambda x: bucket(float(x)))
    zone_order = ["Very High", "High", "Target", "Low", "Very Low"]
    zone_pct = period_df["zone"].value_counts(normalize=True).reindex(zone_order).fillna(0) * 100

    h1, h2, h3 = st.columns(3)
    h1.markdown(f"<div class='emr-chip'><strong>Patient</strong><br>{selected_patient}</div>", unsafe_allow_html=True)
    h2.markdown(f"<div class='emr-chip'><strong>TIR period</strong><br>{report_period}</div>", unsafe_allow_html=True)
    h3.markdown(f"<div class='emr-chip'><strong>Target</strong><br>{cfg['target'][0]} - {cfg['target'][1]} {cfg['unit']}</div>", unsafe_allow_html=True)

    fig = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"secondary_y": True}, {"secondary_y": True}]],
        column_widths=[0.34, 0.66],
        subplot_titles=(f"Time in Ranges ({tir_period})", f"Longitudinal {vital.replace('_', ' ').title()} Profile"),
        horizontal_spacing=0.12,
    )

    zone_colors = {"Very Low": "#5b8cc0", "Low": "#9db8d6", "Target": "#5fa25f", "High": "#f0b35a", "Very High": "#d86a5f"}

    for z in zone_order[::-1]:
        fig.add_trace(go.Bar(x=[report_period], y=[float(zone_pct[z])], name=z, marker_color=zone_colors[z], hovertemplate=f"{z}: %{{y:.1f}}%<extra></extra>"), row=1, col=1, secondary_y=True)

    left_min = min(v for v,_ in cfg["zones"].values() if abs(v) < 1e8)
    left_max = max(h for _,h in cfg["zones"].values() if abs(h) < 1e8)
    fig.add_trace(go.Scatter(x=[report_period, report_period], y=[cfg["target"][0], cfg["target"][1]], mode="lines", line=dict(color="#2f5d96", width=0.1), showlegend=False, hoverinfo="skip"), row=1, col=1, secondary_y=False)

    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p95"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p05"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(142,173,201,0.35)", name="5-95%"), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p75"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p25"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(230,177,112,0.45)", name="25-75%"), row=1, col=2, secondary_y=False)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p50"], mode="lines", line=dict(color="#1f6fb2", width=2.8), name="Median (50%)"), row=1, col=2, secondary_y=False)

    fig.add_hline(y=cfg["target"][0], line=dict(color="#2f5d96", width=1.5), row=1, col=2)
    fig.add_hline(y=cfg["target"][1], line=dict(color="#2f5d96", width=1.5), row=1, col=2)
    fig.add_hrect(y0=cfg["target"][0], y1=cfg["target"][1], fillcolor="rgba(95,162,95,0.18)", line_width=0, row=1, col=2)

    fig.update_layout(height=620, barmode="stack", paper_bgcolor="#f2f4f8", plot_bgcolor="#f2f4f8", legend_title_text="Range", font=dict(family="Arial, sans-serif", size=13, color="#21324d"), margin=dict(l=30, r=30, t=60, b=40))

    fig.update_yaxes(title_text=f"{vital.replace('_', ' ').title()} ({cfg['unit']})", row=1, col=1, secondary_y=False, range=[left_min-5, left_max+5])
    fig.update_yaxes(title_text="Percent of readings (%)", row=1, col=1, secondary_y=True, range=[0, 100])

    fig.update_yaxes(title_text=f"{vital.replace('_', ' ').title()} ({cfg['unit']})", row=1, col=2, secondary_y=False, showgrid=True, gridcolor="#d4deea")
    fig.update_yaxes(title_text="Percentiles", row=1, col=2, secondary_y=True, tickvals=[95, 75, 50, 25, 5], ticktext=["95%", "75%", "50%", "25%", "5%"], range=[0, 100])

    fig.update_xaxes(title_text="Period", row=1, col=1)
    fig.update_xaxes(title_text="Time", row=1, col=2, showgrid=True, gridcolor="#d4deea")

    st.plotly_chart(fig, width='stretch')
st.subheader("Medication Suggestions (Simulated Rules)")
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

st.subheader("Export")
csv_bytes = df.sort_values(["patient_id", "timestamp"]).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download current data as CSV",
    data=csv_bytes,
    file_name="vitals_export.csv",
    mime="text/csv",
)
