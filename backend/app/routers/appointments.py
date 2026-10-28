from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="/api/appointments", tags=["appointments"])


@router.post("/", response_model=schemas.AppointmentOut, status_code=201)
def create_appointment(
    payload: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    patient = db.query(models.Patient).filter(models.Patient.patient_id == payload.patient_id.upper()).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    appt = models.Appointment(**payload.model_dump())
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt


@router.get("/", response_model=List[schemas.AppointmentOut])
def list_appointments(
    patient_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = db.query(models.Appointment)
    if patient_id:
        q = q.filter(models.Appointment.patient_id == patient_id.upper())
    if status:
        q = q.filter(models.Appointment.status == status)
    return q.order_by(models.Appointment.appointment_date.desc()).offset(skip).limit(limit).all()


@router.get("/{appt_id}", response_model=schemas.AppointmentOut)
def get_appointment(appt_id: int, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    appt = db.query(models.Appointment).filter(models.Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appt


@router.put("/{appt_id}", response_model=schemas.AppointmentOut)
def update_appointment(
    appt_id: int,
    payload: schemas.AppointmentUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    appt = db.query(models.Appointment).filter(models.Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(appt, field, value)
    db.commit()
    db.refresh(appt)
    return appt


@router.delete("/{appt_id}", status_code=204)
def cancel_appointment(
    appt_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    appt = db.query(models.Appointment).filter(models.Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt.status = models.AppointmentStatusEnum.cancelled
    db.commit()
