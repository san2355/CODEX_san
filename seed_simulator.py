from __future__ import annotations

import random
import time
from datetime import datetime

import requests

API_BASE = "http://localhost:8000"
PATIENTS = ["HF001", "HF002", "HF003", "HF004"]
last_weight = {pid: 75 + random.uniform(-2, 2) for pid in PATIENTS}


def make_payload(patient_id: str) -> dict:
    last_weight[patient_id] += random.uniform(-0.2, 0.45)
    return {
        "patient_id": patient_id,
        "systolic": random.randint(115, 185),
        "diastolic": random.randint(70, 112),
        "heart_rate": random.randint(52, 130),
        "weight": round(last_weight[patient_id], 2),
        "spo2": random.randint(87, 99),
        "timestamp": datetime.utcnow().isoformat(),
    }


def seed_once() -> None:
    for pid in PATIENTS:
        payload = make_payload(pid)
        response = requests.post(f"{API_BASE}/ingest/vitals", json=payload, timeout=10)
        response.raise_for_status()
        print(f"{pid}: {response.json()}")


if __name__ == "__main__":
    print("Seeding simulator started. Press Ctrl+C to stop.")
    while True:
        seed_once()
        time.sleep(3)
