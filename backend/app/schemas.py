from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
from datetime import date, datetime
from .models import GenderEnum, AppointmentStatusEnum


# ── Auth ──────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    role: str = "staff"

class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None


# ── Patient ───────────────────────────────────────────────────────────────────
class PatientBase(BaseModel):
    patient_id: str
    full_name: str
    date_of_birth: date
    gender: GenderEnum
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None

    @field_validator("patient_id")
    @classmethod
    def pid_format(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("patient_id cannot be empty")
        return v

class PatientCreate(PatientBase):
    pass

class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[GenderEnum] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    blood_group: Optional[str] = None

class PatientOut(PatientBase):
    id: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Appointment ───────────────────────────────────────────────────────────────
class AppointmentBase(BaseModel):
    patient_id: str
    doctor_name: str
    department: str
    appointment_date: datetime
    reason: Optional[str] = None
    notes: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentUpdate(BaseModel):
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    appointment_date: Optional[datetime] = None
    reason: Optional[str] = None
    status: Optional[AppointmentStatusEnum] = None
    notes: Optional[str] = None

class AppointmentOut(AppointmentBase):
    id: int
    status: AppointmentStatusEnum
    created_at: datetime
    model_config = {"from_attributes": True}
