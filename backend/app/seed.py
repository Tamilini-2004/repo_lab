"""Seed the database with an admin user and sample patients/appointments."""
from datetime import date, datetime, timezone
from .database import SessionLocal, engine, Base
from . import models
from .auth import hash_password


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Admin user
        if not db.query(models.User).filter_by(username="admin").first():
            db.add(models.User(username="admin", full_name="Admin User", role="admin",
                               hashed_password=hash_password("Admin@123")))

        # Staff user
        if not db.query(models.User).filter_by(username="staff1").first():
            db.add(models.User(username="staff1", full_name="Nurse Joy", role="staff",
                               hashed_password=hash_password("Staff@123")))

        db.commit()

        # Sample patients
        patients = [
            {"patient_id": "P001", "full_name": "Alice Johnson", "date_of_birth": date(1985, 3, 12),
             "gender": "female", "phone": "555-0101", "email": "alice@example.com",
             "blood_group": "A+", "address": "12 Maple St, Springfield"},
            {"patient_id": "P002", "full_name": "Bob Martinez", "date_of_birth": date(1972, 7, 25),
             "gender": "male", "phone": "555-0102", "email": "bob@example.com",
             "blood_group": "O-", "address": "34 Oak Ave, Shelbyville"},
            {"patient_id": "P003", "full_name": "Carol White", "date_of_birth": date(1990, 11, 5),
             "gender": "female", "phone": "555-0103", "email": "carol@example.com",
             "blood_group": "B+", "address": "56 Pine Rd, Capital City"},
            {"patient_id": "P004", "full_name": "David Lee", "date_of_birth": date(1965, 1, 30),
             "gender": "male", "phone": "555-0104", "email": "david@example.com",
             "blood_group": "AB+", "address": "78 Elm Blvd, Ogdenville"},
            {"patient_id": "P005", "full_name": "Eva Brown", "date_of_birth": date(2000, 6, 18),
             "gender": "female", "phone": "555-0105", "email": "eva@example.com",
             "blood_group": "O+", "address": "90 Cedar Ln, North Haverbrook"},
        ]
        for p in patients:
            if not db.query(models.Patient).filter_by(patient_id=p["patient_id"]).first():
                db.add(models.Patient(**p))
        db.commit()

        # Sample appointments
        appointments = [
            {"patient_id": "P001", "doctor_name": "Dr. Smith", "department": "Cardiology",
             "appointment_date": datetime(2025, 8, 10, 9, 0, tzinfo=timezone.utc), "reason": "Chest pain follow-up",
             "status": "scheduled"},
            {"patient_id": "P002", "doctor_name": "Dr. Patel", "department": "Orthopedics",
             "appointment_date": datetime(2025, 8, 11, 10, 30, tzinfo=timezone.utc), "reason": "Knee pain",
             "status": "scheduled"},
            {"patient_id": "P003", "doctor_name": "Dr. Kim", "department": "Neurology",
             "appointment_date": datetime(2025, 8, 12, 14, 0, tzinfo=timezone.utc), "reason": "Migraine evaluation",
             "status": "completed"},
            {"patient_id": "P004", "doctor_name": "Dr. Smith", "department": "Cardiology",
             "appointment_date": datetime(2025, 8, 13, 11, 0, tzinfo=timezone.utc), "reason": "Annual checkup",
             "status": "scheduled"},
            {"patient_id": "P005", "doctor_name": "Dr. Nguyen", "department": "General Medicine",
             "appointment_date": datetime(2025, 8, 14, 8, 30, tzinfo=timezone.utc), "reason": "Fever and cold",
             "status": "cancelled"},
        ]
        for a in appointments:
            existing = db.query(models.Appointment).filter_by(
                patient_id=a["patient_id"], appointment_date=a["appointment_date"]
            ).first()
            if not existing:
                db.add(models.Appointment(**a))
        db.commit()
        print("✅ Database seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
