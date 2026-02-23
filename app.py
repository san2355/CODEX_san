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
    .hero-card {
        background: linear-gradient(135deg, #0f4c81 0%, #1aa6b7 100%);
        color: white;
        padding: 1rem 1.2rem;
        border-radius: 14px;
        margin-bottom: 1rem;
        box-shadow: 0 6px 18px rgba(15,76,129,0.25);
    }
    .metric-chip {
        background: #eef7fb;
        border: 1px solid #d3eaf5;
        border-radius: 10px;
        padding: 0.5rem 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class='hero-card'>
      <h3 style='margin:0;'>🧭 Longitudinal Patient Analysis</h3>
      <p style='margin:0.35rem 0 0 0;'>Healthcare startup-style analytics view for clinician trend review across years, months, weeks, or days.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

selected_patient = st.selectbox(
    "Select patient for deep trend review",
    options=sorted(df["patient_id"].unique().tolist()),
)

patient_df = df[df["patient_id"] == selected_patient].sort_values("timestamp").copy()
min_ts = patient_df["timestamp"].min().to_pydatetime()
max_ts = patient_df["timestamp"].max().to_pydatetime()

analysis_cols = st.columns([1.1, 1.1, 1, 1])
with analysis_cols[0]:
    window_mode = st.selectbox(
        "Time window",
        ["All data", "Last 30 days", "Last 90 days", "Last 180 days", "Last 365 days", "Custom range"],
        index=0,
    )
with analysis_cols[1]:
    cadence = st.selectbox("X-axis cadence", ["Raw readings", "Daily", "Weekly", "Monthly"], index=2)
with analysis_cols[2]:
    y_metric = st.selectbox("Vital sign", ["systolic", "diastolic", "heart_rate", "weight"], index=0)
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


def zone_config(metric: str, source_df: pd.DataFrame):
    if metric == "systolic":
        return {"Very Low": (-1e9, 79), "Low": (80, 89), "Target": (90, 140), "High": (141, 160), "Very High": (161, 1e9)}, (90, 140), "mmHg"
    if metric == "diastolic":
        return {"Very Low": (-1e9, 49), "Low": (50, 59), "Target": (60, 90), "High": (91, 100), "Very High": (101, 1e9)}, (60, 90), "mmHg"
    if metric == "heart_rate":
        return {"Very Low": (-1e9, 49), "Low": (50, 59), "Target": (60, 100), "High": (101, 120), "Very High": (121, 1e9)}, (60, 100), "bpm"

    baseline = float(source_df["weight"].median())
    return {
        "Very Low": (-1e9, baseline - 3),
        "Low": (baseline - 3, baseline - 1.5),
        "Target": (baseline - 1.5, baseline + 1.5),
        "High": (baseline + 1.5, baseline + 3),
        "Very High": (baseline + 3, 1e9),
    }, (baseline - 1.5, baseline + 1.5), "kg"


def classify_zone(value: float, cfg: dict[str, tuple[float, float]]) -> str:
    for name, (low, high) in cfg.items():
        if low <= value <= high:
            return name
    return "Very High"

if filtered_patient.empty:
    st.warning("No readings for the selected patient in that time range.")
else:
    cfg, target_band, unit = zone_config(y_metric, patient_df)
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

    scope = filtered_patient[["timestamp", y_metric]].copy()
    scope["period"] = scope["timestamp"].dt.to_period("M").astype(str)
    period_counts = scope.groupby("period")[y_metric].count().sort_index()
    eligible_periods = period_counts[period_counts >= 10]
    report_period = eligible_periods.index.max() if not eligible_periods.empty else period_counts.index.max()
    report_df = scope[scope["period"] == report_period].copy()
    report_df["zone"] = report_df[y_metric].apply(lambda v: classify_zone(float(v), cfg))

    zone_order = ["Very High", "High", "Target", "Low", "Very Low"]
    zone_pct = report_df["zone"].value_counts(normalize=True).reindex(zone_order).fillna(0) * 100

    m1, m2, m3 = st.columns([1, 1, 1])
    m1.markdown(f"<div class='metric-chip'><b>Patient</b><br>{selected_patient}</div>", unsafe_allow_html=True)
    m2.markdown(f"<div class='metric-chip'><b>Report period</b><br>{report_period}</div>", unsafe_allow_html=True)
    m3.markdown(f"<div class='metric-chip'><b>Target range</b><br>{target_band[0]:.1f} - {target_band[1]:.1f} {unit}</div>", unsafe_allow_html=True)

    fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.32, 0.68],
        subplot_titles=(
            f"Time in Ranges — {y_metric.replace('_', ' ').title()}",
            f"Longitudinal {y_metric.replace('_', ' ').title()} profile",
        ),
        horizontal_spacing=0.14,
    )

    colors = {
        "Very Low": "#e74c3c",
        "Low": "#f39c12",
        "Target": "#58b368",
        "High": "#f39c12",
        "Very High": "#d35400",
    }

    for zone in zone_order[::-1]:
        fig.add_trace(
            go.Bar(
                x=[report_period],
                y=[float(zone_pct[zone])],
                name=zone,
                marker_color=colors[zone],
                hovertemplate=f"{zone}: %{{y:.1f}}%<extra></extra>",
            ),
            row=1,
            col=1,
        )

    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p95"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p05"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(244,162,97,0.25)", name="5-95%"), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p75"], mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["p25"], mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(240,201,135,0.45)", name="25-75%"), row=1, col=2)
    fig.add_trace(go.Scatter(x=trend["period"], y=trend["median"], mode="lines", line=dict(color="#17803d", width=3), name="Median"), row=1, col=2)

    fig.add_hrect(y0=target_band[0], y1=target_band[1], line_width=0, fillcolor="rgba(88,179,104,0.18)", row=1, col=2)

    y_min = float(filtered_patient[y_metric].min())
    y_max = float(filtered_patient[y_metric].max())
    y_pad = max((y_max - y_min) * 0.15, 1)
    y_range = st.slider(
        "Y-axis zoom",
        min_value=float(max(0, y_min - y_pad)),
        max_value=float(y_max + y_pad),
        value=(float(max(0, y_min - y_pad / 2)), float(y_max + y_pad / 2)),
        step=0.5,
    )

    fig.update_layout(
        barmode="stack",
        height=600,
        paper_bgcolor="#f8fbfd",
        plot_bgcolor="#f8fbfd",
        title=(
            f"Patient {selected_patient} • {window_mode} • {cadence} cadence "
            f"(readings: {len(filtered_patient)})"
        ),
    )
    fig.update_xaxes(title_text="Report Period", row=1, col=1)
    fig.update_yaxes(title_text="Percent of readings (%)", range=[0, 100], row=1, col=1)
    fig.update_xaxes(title_text="Time", row=1, col=2)
    fig.update_yaxes(title_text=f"{y_metric.replace('_', ' ').title()} ({unit})", range=list(y_range), row=1, col=2)

    st.plotly_chart(fig, width='stretch')

    st.caption(
        "AGP-inspired longitudinal review: stacked bar summarizes time-in-range for the latest reporting month, "
        "and percentile ribbons display variability over time for the selected vital."
    )

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

st.subheader("Export")
csv_bytes = df.sort_values(["patient_id", "timestamp"]).to_csv(index=False).encode("utf-8")
st.download_button(
    "Download current data as CSV",
    data=csv_bytes,
    file_name="vitals_export.csv",
    mime="text/csv",
)
