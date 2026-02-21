from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


st.set_page_config(layout="wide", page_title="Clinic RPM Workflow")
st.title("🫀 Clinic RPM Workflow")

if "api_base" not in st.session_state:
    st.session_state.api_base = os.getenv("API_BASE_URL", "http://localhost:8000")


def api_get(path: str, **kwargs):
    return requests.get(f"{st.session_state.api_base}{path}", timeout=10, **kwargs)


def api_post(path: str, json_payload: dict):
    return requests.post(f"{st.session_state.api_base}{path}", json=json_payload, timeout=10)


def severity_label(value: int) -> str:
    return {3: "🔴 High", 2: "🟡 Medium", 1: "🟢 Low"}.get(value, str(value))


triage_tab, patients_tab, patient_detail_tab, settings_tab = st.tabs(
    ["Triage Queue", "Patients", "Patient Detail", "Settings"]
)

with triage_tab:
    st.subheader("Unresolved Alert Queue")
    try:
        alerts = api_get("/alerts").json()
        active_alerts = [a for a in alerts if a["status"] != "resolved"]
        active_alerts.sort(key=lambda a: (a["severity"], a["created_at"]), reverse=True)
    except Exception as exc:
        st.error(f"Unable to load alerts: {exc}")
        active_alerts = []

    if not active_alerts:
        st.success("No unresolved alerts.")

    for alert in active_alerts:
        cols = st.columns([2, 3, 2, 4, 6])
        cols[0].markdown(f"**#{alert['id']}**")
        cols[1].write(alert["patient_id"])
        cols[2].write(severity_label(alert["severity"]))
        cols[3].write(alert["status"])
        cols[4].write(alert["message"])

        action_cols = st.columns([1, 1, 1, 3])
        if action_cols[0].button("Ack", key=f"ack_{alert['id']}"):
            api_post(f"/alerts/{alert['id']}/ack", {"note": "Acknowledged from triage"})
            st.rerun()
        if action_cols[1].button("Snooze 60m", key=f"snooze_{alert['id']}"):
            api_post(f"/alerts/{alert['id']}/snooze", {"snooze_minutes": 60, "note": "Snoozed from triage"})
            st.rerun()
        if action_cols[2].button("Resolve", key=f"resolve_{alert['id']}"):
            api_post(f"/alerts/{alert['id']}/resolve", {"note": "Resolved from triage"})
            st.rerun()
        st.divider()

with patients_tab:
    st.subheader("Patient Census (Latest Vitals)")
    try:
        latest = api_get("/patients/latest").json()
        latest_df = pd.DataFrame(latest)
        if latest_df.empty:
            st.info("No patient data yet. Run simulator first.")
        else:
            st.dataframe(latest_df.sort_values("patient_id"), use_container_width=True)
    except Exception as exc:
        st.error(f"Unable to load patient data: {exc}")

with patient_detail_tab:
    st.subheader("Patient Detail")
    selected_patient = st.text_input("Patient ID", value="HF001")
    if st.button("Load Patient", key="load_patient"):
        st.session_state.selected_patient = selected_patient

    patient_id = st.session_state.get("selected_patient", selected_patient)

    try:
        history = api_get(f"/patients/{patient_id}/history").json()
        vitals_df = pd.DataFrame(history.get("vitals", []))
        alerts_df = pd.DataFrame(history.get("alerts", []))
        actions_df = pd.DataFrame(history.get("actions", []))

        if not vitals_df.empty:
            vitals_df["timestamp"] = pd.to_datetime(vitals_df["timestamp"])
            st.markdown("**7-day trends**")
            trend_cols = st.columns(3)
            for idx, metric in enumerate(["systolic", "heart_rate", "weight"]):
                fig = px.line(vitals_df, x="timestamp", y=metric, title=metric.upper())
                trend_cols[idx].plotly_chart(fig, use_container_width=True)

            st.markdown("**BP trend**")
            bp_fig = px.line(vitals_df, x="timestamp", y=["systolic", "diastolic"], title="Blood pressure")
            st.plotly_chart(bp_fig, use_container_width=True)
        else:
            st.info("No vitals in the last 7 days for this patient.")

        st.markdown("**Alert history**")
        if alerts_df.empty:
            st.write("No alerts yet.")
        else:
            st.dataframe(alerts_df, use_container_width=True)

        st.markdown("**Action log**")
        if actions_df.empty:
            st.write("No logged actions.")
        else:
            st.dataframe(actions_df, use_container_width=True)
    except Exception as exc:
        st.error(f"Unable to load patient history: {exc}")

with settings_tab:
    st.subheader("Settings")
    new_url = st.text_input("API Base URL", value=st.session_state.api_base)
    if st.button("Save Settings"):
        st.session_state.api_base = new_url.rstrip("/")
        st.success(f"API base URL updated to {st.session_state.api_base}")

    st.caption("Run backend with: uvicorn api:app --reload")
    st.caption("Run UI with: streamlit run app.py")
