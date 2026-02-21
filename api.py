from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Float, Integer, String, Text, create_engine, desc, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = "sqlite:///./telemonitoring.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class AlertStatus(str, Enum):
    new = "new"
    ack = "ack"
    snoozed = "snoozed"
    resolved = "resolved"


class Vital(Base):
    __tablename__ = "vitals"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    systolic: Mapped[int] = mapped_column(Integer)
    diastolic: Mapped[int] = mapped_column(Integer)
    heart_rate: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float)
    spo2: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default=AlertStatus.new.value, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    snooze_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    message: Mapped[str] = mapped_column(Text)


class ActionLog(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    alert_id: Mapped[int] = mapped_column(Integer, index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Clinic-Style RPM API")


class VitalIn(BaseModel):
    patient_id: str
    systolic: int
    diastolic: int
    heart_rate: int
    weight: float
    spo2: int
    timestamp: datetime


class AlertActionIn(BaseModel):
    note: Optional[str] = None
    snooze_minutes: int = Field(default=60, ge=1, le=24 * 60)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def create_alert_if_needed(db: Session, vital: Vital) -> list[Alert]:
    alerts_created: list[Alert] = []

    rules = [
        ("bp", 3, vital.systolic >= 180 or vital.diastolic >= 110, f"Hypertensive crisis range BP {vital.systolic}/{vital.diastolic}"),
        ("bp", 2, vital.systolic >= 160 or vital.diastolic >= 100, f"Elevated blood pressure {vital.systolic}/{vital.diastolic}"),
        ("hr", 2, vital.heart_rate >= 120 or vital.heart_rate <= 45, f"Abnormal heart rate {vital.heart_rate} bpm"),
        ("spo2", 3, vital.spo2 < 90, f"Low oxygen saturation {vital.spo2}%"),
        ("weight", 2, False, ""),
    ]

    last_weight = (
        db.query(Vital)
        .filter(Vital.patient_id == vital.patient_id, Vital.id != vital.id)
        .order_by(desc(Vital.timestamp))
        .first()
    )
    if last_weight is not None and (vital.weight - last_weight.weight) >= 2.0:
        rules[-1] = ("weight", 2, True, f"Rapid weight gain +{vital.weight - last_weight.weight:.1f} kg")

    for alert_type, severity, condition, message in rules:
        if not condition:
            continue
        alert = Alert(
            patient_id=vital.patient_id,
            type=alert_type,
            severity=severity,
            status=AlertStatus.new.value,
            message=message,
        )
        db.add(alert)
        db.flush()
        db.add(ActionLog(alert_id=alert.id, patient_id=alert.patient_id, action_type="created", note=message))
        alerts_created.append(alert)

    return alerts_created


@app.post("/ingest/vitals")
def ingest_vitals(payload: VitalIn, db: Session = Depends(get_db)):
    vital = Vital(**payload.model_dump())
    db.add(vital)
    db.flush()

    alerts = create_alert_if_needed(db, vital)
    db.commit()
    return {"status": "ok", "vital_id": vital.id, "alerts_created": [a.id for a in alerts]}


@app.get("/patients/latest")
def get_latest_patients(db: Session = Depends(get_db)):
    latest_ids = (
        db.query(func.max(Vital.id).label("id"))
        .group_by(Vital.patient_id)
        .subquery()
    )
    vitals = db.query(Vital).join(latest_ids, Vital.id == latest_ids.c.id).all()
    return [
        {
            "patient_id": v.patient_id,
            "systolic": v.systolic,
            "diastolic": v.diastolic,
            "heart_rate": v.heart_rate,
            "weight": v.weight,
            "spo2": v.spo2,
            "timestamp": v.timestamp,
        }
        for v in vitals
    ]


@app.get("/alerts")
def list_alerts(status: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    alerts = query.order_by(desc(Alert.severity), desc(Alert.created_at)).all()
    return [
        {
            "id": a.id,
            "patient_id": a.patient_id,
            "type": a.type,
            "severity": a.severity,
            "status": a.status,
            "created_at": a.created_at,
            "resolved_at": a.resolved_at,
            "snooze_until": a.snooze_until,
            "message": a.message,
        }
        for a in alerts
    ]


@app.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, action: AlertActionIn, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.ack.value
    alert.snooze_until = None
    db.add(ActionLog(alert_id=alert.id, patient_id=alert.patient_id, action_type="ack", note=action.note))
    db.commit()
    return {"status": "ok"}


@app.post("/alerts/{alert_id}/snooze")
def snooze_alert(alert_id: int, action: AlertActionIn, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.snoozed.value
    alert.snooze_until = datetime.utcnow() + timedelta(minutes=action.snooze_minutes)
    db.add(
        ActionLog(
            alert_id=alert.id,
            patient_id=alert.patient_id,
            action_type="snooze",
            note=action.note or f"{action.snooze_minutes} minutes",
        )
    )
    db.commit()
    return {"status": "ok", "snooze_until": alert.snooze_until}


@app.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, action: AlertActionIn, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = AlertStatus.resolved.value
    alert.resolved_at = datetime.utcnow()
    alert.snooze_until = None
    db.add(ActionLog(alert_id=alert.id, patient_id=alert.patient_id, action_type="resolve", note=action.note))
    db.commit()
    return {"status": "ok", "resolved_at": alert.resolved_at}


@app.get("/patients/{patient_id}/history")
def patient_history(patient_id: str, db: Session = Depends(get_db)):
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    vitals = (
        db.query(Vital)
        .filter(Vital.patient_id == patient_id, Vital.timestamp >= seven_days_ago)
        .order_by(Vital.timestamp)
        .all()
    )
    alerts = db.query(Alert).filter(Alert.patient_id == patient_id).order_by(desc(Alert.created_at)).all()
    actions = (
        db.query(ActionLog)
        .filter(ActionLog.patient_id == patient_id)
        .order_by(desc(ActionLog.created_at))
        .all()
    )

    return {
        "patient_id": patient_id,
        "vitals": [
            {
                "timestamp": v.timestamp,
                "systolic": v.systolic,
                "diastolic": v.diastolic,
                "heart_rate": v.heart_rate,
                "weight": v.weight,
                "spo2": v.spo2,
            }
            for v in vitals
        ],
        "alerts": [
            {
                "id": a.id,
                "type": a.type,
                "severity": a.severity,
                "status": a.status,
                "created_at": a.created_at,
                "resolved_at": a.resolved_at,
                "snooze_until": a.snooze_until,
                "message": a.message,
            }
            for a in alerts
        ],
        "actions": [
            {
                "id": act.id,
                "alert_id": act.alert_id,
                "action_type": act.action_type,
                "note": act.note,
                "created_at": act.created_at,
            }
            for act in actions
        ],
    }
