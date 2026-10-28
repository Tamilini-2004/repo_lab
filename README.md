# Hospital Patient Management System

**Stack:** FastAPI · PostgreSQL (Amazon RDS) · HTML/CSS/JS · Docker · EC2

---

## Project Structure

```
cc_2_lab_exam_25mx352/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, CORS, static files
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   ├── models.py        # ORM models: User, Patient, Appointment
│   │   ├── schemas.py       # Pydantic request/response schemas
│   │   ├── auth.py          # JWT auth, password hashing
│   │   ├── seed.py          # Sample data seeder
│   │   └── routers/
│   │       ├── auth.py      # /api/auth/login, /register, /me
│   │       ├── patients.py  # /api/patients CRUD
│   │       └── appointments.py  # /api/appointments CRUD
│   ├── tests/
│   │   └── test_api.py      # Full integration test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── index.html           # Single-page dashboard
│   ├── style.css
│   └── app.js               # Vanilla JS API client
├── docker-compose.yml       # Local dev (includes local PostgreSQL)
├── docker-compose.prod.yml  # Production (points to RDS)
├── .env.example             # Local env template
├── .env.prod.example        # Production env template
└── .gitignore
```

---

## Default Credentials (seeded automatically)

| Role  | Username | Password   |
|-------|----------|------------|
| Admin | admin    | Admin@123  |
| Staff | staff1   | Staff@123  |

---

## STAGE 1 — Local Development with Docker

### Prerequisites
- Docker Desktop installed and running
- Git

### Steps

```bash
# 1. Clone / enter the project
cd cc_2_lab_exam_25mx352

# 2. Start all services (PostgreSQL + Backend + pgAdmin)
docker compose up --build -d

# 3. Wait ~15 seconds for DB to be ready, then open:
#    Frontend + API  →  http://localhost:8000
#    pgAdmin         →  http://localhost:5050
#    API Docs        →  http://localhost:8000/docs
```

### pgAdmin local setup
1. Open http://localhost:5050
2. Login: `admin@hospital.local` / `pgadmin123`
3. Right-click Servers → Register → Server
   - Name: `HPMS Local`
   - Host: `db`  (Docker service name)
   - Port: `5432`
   - Database: `hpms_db`
   - Username: `hpms_user`
   - Password: `hpms_pass`
4. Navigate: Servers → HPMS Local → Databases → hpms_db → Schemas → public → Tables

### Run tests locally
```bash
# Install test dependencies (outside Docker, in a venv)
cd backend
pip install -r requirements.txt -r tests/requirements-test.txt

# Run tests (stack must be running)
pytest tests/ -v
```

### Stop local stack
```bash
docker compose down          # keep data
docker compose down -v       # also delete DB volume
```

---

## STAGE 2 — AWS Setup

### 2A. Create Amazon RDS PostgreSQL Instance

1. Open **AWS Console → RDS → Create database**
2. Settings:
   - Engine: **PostgreSQL 15**
   - Template: **Free tier** (for testing) or Production
   - DB instance identifier: `hpms-db`
   - Master username: `hpms_admin`
   - Master password: choose a strong password (save it)
   - DB name: `hpms_production`
   - Instance class: `db.t3.micro`
   - Storage: 20 GB gp2
   - **Public access: NO** ← important
   - VPC: default (or same VPC as your EC2)
   - VPC security group: create new → name it `hpms-rds-sg`
3. Click **Create database** — wait ~5 minutes
4. Note the **Endpoint** (e.g. `hpms-db.xxxx.us-east-1.rds.amazonaws.com`)

### 2B. Create EC2 Instance

1. Open **AWS Console → EC2 → Launch Instance**
2. Settings:
   - Name: `hpms-server`
   - AMI: **Ubuntu 22.04 LTS**
   - Instance type: `t2.micro` (free tier)
   - Key pair: create new → download `.pem` file
   - Security group: create new → name `hpms-ec2-sg`
     - Inbound rules:
       - SSH (22) from your IP
       - HTTP (80) from 0.0.0.0/0
       - Custom TCP (8000) from 0.0.0.0/0
3. Launch instance — note the **Public IPv4 address**

### 2C. Configure RDS Security Group to Allow EC2

1. Go to **EC2 → Security Groups → hpms-rds-sg**
2. Edit Inbound Rules → Add Rule:
   - Type: PostgreSQL (5432)
   - Source: **Security group ID of hpms-ec2-sg**
3. Save — this allows only your EC2 to reach RDS, not the public internet

### 2D. Connect to EC2 and Install Docker

```bash
# From your local machine (replace with your key and EC2 IP)
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# On EC2:
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker ubuntu
newgrp docker
```

### 2E. Deploy Application to EC2

```bash
# On EC2 — clone your repo
git clone https://github.com/<your-username>/cc_2_lab_exam_25mx352.git
cd cc_2_lab_exam_25mx352

# Create production environment file (NEVER commit this)
cat > .env.prod << 'EOF'
DATABASE_URL=postgresql://hpms_admin:<YOUR_RDS_PASSWORD>@<RDS_ENDPOINT>:5432/hpms_production
SECRET_KEY=<generate-with: python3 -c "import secrets; print(secrets.token_hex(32))">
ACCESS_TOKEN_EXPIRE_MINUTES=480
EOF

# Start production stack (connects to RDS, no local DB container)
docker compose -f docker-compose.prod.yml up --build -d

# Verify it's running
docker compose -f docker-compose.prod.yml logs -f
```

### 2F. Verify RDS Connectivity from EC2

```bash
# Test DB connection directly
docker exec hpms_backend python -c "
from app.database import engine
with engine.connect() as c:
    print('RDS connection OK')
"
```

### 2G. Connect pgAdmin to RDS

1. Open pgAdmin on your local machine (or install at http://localhost:5050 via local Docker)
2. Register → Server:
   - Name: `HPMS RDS Production`
   - Host: `<RDS_ENDPOINT>` (e.g. hpms-db.xxxx.us-east-1.rds.amazonaws.com)
   - Port: `5432`
   - Database: `hpms_production`
   - Username: `hpms_admin`
   - Password: your RDS password
   - **Note:** pgAdmin must be run from within the same VPC or via SSH tunnel to connect to a private RDS instance

### SSH Tunnel for pgAdmin (if RDS is private)
```bash
# On your local machine — open SSH tunnel
ssh -i your-key.pem -L 5433:<RDS_ENDPOINT>:5432 ubuntu@<EC2_PUBLIC_IP> -N

# Then in pgAdmin connect to:
# Host: localhost  Port: 5433  DB: hpms_production
```

---

## STAGE 3 — Database Schema

Tables are created automatically by SQLAlchemy on first startup.

### Manual schema creation (alternative)
```sql
-- Run in pgAdmin Query Tool or psql

CREATE TYPE genderenum AS ENUM ('male', 'female', 'other');
CREATE TYPE appointmentstatusenum AS ENUM ('scheduled', 'cancelled', 'completed');

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'staff',
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    gender genderenum NOT NULL,
    phone VARCHAR(20) NOT NULL,
    email VARCHAR(100),
    address TEXT,
    blood_group VARCHAR(5),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    doctor_name VARCHAR(100) NOT NULL,
    department VARCHAR(100) NOT NULL,
    appointment_date TIMESTAMPTZ NOT NULL,
    reason TEXT,
    status appointmentstatusenum NOT NULL DEFAULT 'scheduled',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Useful pgAdmin queries for demonstration
```sql
-- View all patients
SELECT * FROM patients ORDER BY created_at DESC;

-- View all appointments with patient names
SELECT a.id, p.full_name, a.doctor_name, a.department, a.appointment_date, a.status
FROM appointments a JOIN patients p ON a.patient_id = p.patient_id
ORDER BY a.appointment_date DESC;

-- Count by status
SELECT status, COUNT(*) FROM appointments GROUP BY status;
```

---

## STAGE 4 — Academic Demonstration Guide

### 1. Show the deployed website
- Open `http://<EC2_PUBLIC_IP>:8000` in browser
- Login with `admin` / `Admin@123`
- Show the dashboard with stats and recent records

### 2. Patient Creation → verify in RDS
- Click **Patients → + Add Patient**
- Fill: ID=`DEMO001`, Name=`John Demo`, DOB=`1988-05-15`, Gender=Male, Phone=`555-1234`, Blood=`A+`
- Click Save
- In pgAdmin: `SELECT * FROM patients WHERE patient_id = 'DEMO001';`
- Show the record appears in RDS

### 3. Patient Retrieval
- On website: use search bar to find `DEMO001` or `John Demo`
- In pgAdmin: `SELECT * FROM patients WHERE full_name ILIKE '%Demo%';`

### 4. Patient Update → verify in RDS
- Click ✏️ on DEMO001 → change phone to `555-9999` → Save
- In pgAdmin: `SELECT patient_id, full_name, phone FROM patients WHERE patient_id = 'DEMO001';`
- Show updated phone number

### 5. Patient Deletion → verify in RDS
- Click 🗑️ on DEMO001 → confirm delete
- In pgAdmin: `SELECT * FROM patients WHERE patient_id = 'DEMO001';` → 0 rows

### 6. Appointment Management
- Click **Appointments → + New Appointment**
- Patient ID: `P001`, Doctor: `Dr. Smith`, Dept: `Cardiology`, Date: any future date
- Show it in the appointments table
- Edit it (reschedule date or change status to Completed)
- Show cancellation (delete button sets status to cancelled)
- In pgAdmin: `SELECT * FROM appointments ORDER BY created_at DESC LIMIT 5;`

### 7. Show RDS in AWS Console
- Open AWS Console → RDS → Databases → hpms-db
- Show: DB identifier, engine (PostgreSQL 15), endpoint, port (5432), status (Available)
- Show: VPC, security groups, no public accessibility

### 8. Show tables in pgAdmin
- Expand: Servers → HPMS RDS → hpms_production → Schemas → public → Tables
- Show: `users`, `patients`, `appointments` tables
- Right-click each → View/Edit Data → All Rows
- Show actual records created through the website

### 9. API Tests
```bash
# On EC2 or local machine with stack running:
cd backend
pytest tests/ -v

# Or use the interactive API docs:
# http://localhost:8000/docs  (local)
# http://<EC2_IP>:8000/docs   (production)
```
- Show all tests passing in terminal
- Optionally demonstrate in Swagger UI: authorize with admin token, test each endpoint

---

## API Reference

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /api/auth/login | Get JWT token | None |
| GET | /api/auth/me | Current user info | Any |
| POST | /api/auth/register | Create staff account | Admin |
| GET | /api/patients/ | List / search patients | Any |
| POST | /api/patients/ | Create patient | Any |
| GET | /api/patients/{id} | Get patient | Any |
| PUT | /api/patients/{id} | Update patient | Any |
| DELETE | /api/patients/{id} | Delete patient | Any |
| GET | /api/appointments/ | List appointments | Any |
| POST | /api/appointments/ | Create appointment | Any |
| GET | /api/appointments/{id} | Get appointment | Any |
| PUT | /api/appointments/{id} | Update/reschedule | Any |
| DELETE | /api/appointments/{id} | Cancel appointment | Any |

---

## Security Notes

- Passwords are bcrypt-hashed — never stored in plain text
- JWT tokens expire after 8 hours
- Database credentials are in `.env` / `.env.prod` — never committed to Git
- RDS has no public access — only reachable from EC2 via security group rules
- HTTPS can be added via Nginx reverse proxy + Let's Encrypt on EC2
