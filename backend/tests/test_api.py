"""
Integration tests — run against a live local stack:
  docker compose up -d
  cd backend
  pip install -r requirements.txt -r tests/requirements-test.txt
  pytest tests/ -v
"""
import pytest
import httpx

BASE = "http://localhost:8000"
ADMIN = {"username": "admin", "password": "Admin@123"}
STAFF = {"username": "staff1", "password": "Staff@123"}


def get_token(credentials: dict) -> str:
    r = httpx.post(f"{BASE}/api/auth/login", data=credentials)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {get_token(ADMIN)}"}


@pytest.fixture(scope="module")
def staff_headers():
    return {"Authorization": f"Bearer {get_token(STAFF)}"}


# ── Auth tests ────────────────────────────────────────────────────────────────
class TestAuth:
    def test_login_admin(self):
        r = httpx.post(f"{BASE}/api/auth/login", data=ADMIN)
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_login_invalid(self):
        r = httpx.post(f"{BASE}/api/auth/login", data={"username": "x", "password": "y"})
        assert r.status_code == 401

    def test_me(self, admin_headers):
        r = httpx.get(f"{BASE}/api/auth/me", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["username"] == "admin"

    def test_register_requires_admin(self, staff_headers):
        r = httpx.post(f"{BASE}/api/auth/register",
                       json={"username": "x", "full_name": "X", "password": "x"},
                       headers=staff_headers)
        assert r.status_code == 403

    def test_unauthenticated_rejected(self):
        r = httpx.get(f"{BASE}/api/patients/")
        assert r.status_code == 401


# ── Patient CRUD tests ────────────────────────────────────────────────────────
TEST_PID = "PYTEST001"

class TestPatients:
    def test_create_patient(self, admin_headers):
        payload = {
            "patient_id": TEST_PID,
            "full_name": "Test Patient",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "555-9999",
            "blood_group": "O+",
        }
        r = httpx.post(f"{BASE}/api/patients/", json=payload, headers=admin_headers)
        assert r.status_code == 201
        assert r.json()["patient_id"] == TEST_PID

    def test_duplicate_patient_id(self, admin_headers):
        payload = {
            "patient_id": TEST_PID,
            "full_name": "Duplicate",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone": "555-0000",
        }
        r = httpx.post(f"{BASE}/api/patients/", json=payload, headers=admin_headers)
        assert r.status_code == 400

    def test_list_patients(self, staff_headers):
        r = httpx.get(f"{BASE}/api/patients/", headers=staff_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_patient(self, staff_headers):
        r = httpx.get(f"{BASE}/api/patients/{TEST_PID}", headers=staff_headers)
        assert r.status_code == 200
        assert r.json()["full_name"] == "Test Patient"

    def test_search_patient(self, staff_headers):
        r = httpx.get(f"{BASE}/api/patients/?search=Test", headers=staff_headers)
        assert r.status_code == 200
        ids = [p["patient_id"] for p in r.json()]
        assert TEST_PID in ids

    def test_update_patient(self, admin_headers):
        r = httpx.put(f"{BASE}/api/patients/{TEST_PID}",
                      json={"phone": "555-8888"}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["phone"] == "555-8888"

    def test_get_nonexistent(self, staff_headers):
        r = httpx.get(f"{BASE}/api/patients/DOESNOTEXIST", headers=staff_headers)
        assert r.status_code == 404


# ── Appointment CRUD tests ────────────────────────────────────────────────────
class TestAppointments:
    appt_id = None

    def test_create_appointment(self, admin_headers):
        payload = {
            "patient_id": TEST_PID,
            "doctor_name": "Dr. Test",
            "department": "General",
            "appointment_date": "2025-12-01T10:00:00Z",
            "reason": "Routine checkup",
        }
        r = httpx.post(f"{BASE}/api/appointments/", json=payload, headers=admin_headers)
        assert r.status_code == 201
        TestAppointments.appt_id = r.json()["id"]

    def test_list_appointments(self, staff_headers):
        r = httpx.get(f"{BASE}/api/appointments/", headers=staff_headers)
        assert r.status_code == 200

    def test_filter_by_patient(self, staff_headers):
        r = httpx.get(f"{BASE}/api/appointments/?patient_id={TEST_PID}", headers=staff_headers)
        assert r.status_code == 200
        assert all(a["patient_id"] == TEST_PID for a in r.json())

    def test_update_appointment(self, admin_headers):
        r = httpx.put(f"{BASE}/api/appointments/{self.appt_id}",
                      json={"status": "completed", "notes": "All good"},
                      headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    def test_cancel_appointment(self, admin_headers):
        r = httpx.delete(f"{BASE}/api/appointments/{self.appt_id}", headers=admin_headers)
        assert r.status_code == 204

    def test_delete_patient(self, admin_headers):
        r = httpx.delete(f"{BASE}/api/patients/{TEST_PID}", headers=admin_headers)
        assert r.status_code == 204

    def test_patient_gone_after_delete(self, staff_headers):
        r = httpx.get(f"{BASE}/api/patients/{TEST_PID}", headers=staff_headers)
        assert r.status_code == 404
