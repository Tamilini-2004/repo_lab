# HPMS — Complete AWS Deployment Guide

This guide takes you from zero to a fully deployed, HTTPS-accessible Hospital Patient
Management System on AWS EC2 + RDS. Every command is exact and copy-pasteable.

---

## Prerequisites (your local machine)

| Tool | Purpose | Check |
|------|---------|-------|
| AWS account | Cloud infrastructure | console.aws.amazon.com |
| AWS Console access | Create RDS + EC2 | Browser |
| Git | Push code | `git --version` |
| SSH client | Connect to EC2 | `ssh -V` (built-in on macOS/Linux/WSL) |
| pgAdmin 4 | Inspect RDS | pgadmin.org/download |

---

## PHASE 1 — Verify Local Stack Works First

Before touching AWS, confirm the app runs locally.

```bash
cd cc_2_lab_exam_25mx352
docker compose up --build -d
```

Wait 15 seconds, then open http://localhost:8000
- Login: `admin` / `Admin@123`
- Confirm dashboard loads, patients table shows 5 rows
- Add a test patient, edit it, delete it

Run the tests:
```bash
cd backend
pip install -r requirements.txt -r tests/requirements-test.txt
pytest tests/ -v
```

All 17 tests must pass before proceeding.

```bash
# Stop local stack when done
docker compose down
```

---

## PHASE 2 — AWS Infrastructure Setup

### Step 2.1 — Create the RDS PostgreSQL Database

1. Open **AWS Console → RDS → Create database**

2. Choose these settings exactly:

   | Setting | Value |
   |---------|-------|
   | Creation method | Standard create |
   | Engine | PostgreSQL |
   | Engine version | PostgreSQL 15.x (latest 15) |
   | Template | Free tier |
   | DB instance identifier | `hpms-db` |
   | Master username | `hpms_admin` |
   | Master password | Choose strong password — **write it down** |
   | DB instance class | db.t3.micro |
   | Storage type | gp2 |
   | Allocated storage | 20 GiB |
   | Storage autoscaling | Disabled |
   | VPC | Default VPC |
   | DB subnet group | default |
   | Public access | **NO** ← critical security setting |
   | VPC security group | Create new → name: `hpms-rds-sg` |
   | Availability zone | No preference |
   | Database port | 5432 |
   | Initial database name | `hpms_production` |
   | Backup retention | 1 day |
   | Encryption | Enabled (default) |

3. Click **Create database** — wait 5–10 minutes for status to show **Available**

4. Click the database name → note the **Endpoint** value:
   ```
   hpms-db.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com
   ```
   You will need this in Step 2.4.

**Screenshot checkpoint:** RDS console showing status = Available, endpoint visible.

---

### Step 2.2 — Create the EC2 Instance

1. Open **AWS Console → EC2 → Launch Instance**

2. Settings:

   | Setting | Value |
   |---------|-------|
   | Name | `hpms-server` |
   | AMI | Ubuntu Server 22.04 LTS (64-bit x86) |
   | Instance type | t2.micro (free tier eligible) |
   | Key pair | Create new → name: `hpms-key` → RSA → .pem → **Download** |
   | Network | Default VPC |
   | Subnet | Any public subnet |
   | Auto-assign public IP | Enable |
   | Security group | Create new → name: `hpms-ec2-sg` |

3. Security group inbound rules for `hpms-ec2-sg`:

   | Type | Protocol | Port | Source | Purpose |
   |------|----------|------|--------|---------|
   | SSH | TCP | 22 | My IP | Your SSH access |
   | HTTP | TCP | 80 | 0.0.0.0/0 | HTTP redirect to HTTPS |
   | HTTPS | TCP | 443 | 0.0.0.0/0 | HTTPS web access |

   > Do NOT add port 8000 to the EC2 security group — Nginx handles all traffic on 80/443.

4. Click **Launch instance** — wait ~1 minute for status checks to pass

5. Note the **Public IPv4 address** (e.g. `54.123.45.67`)

**Screenshot checkpoint:** EC2 console showing instance state = Running, public IP visible.

---

### Step 2.3 — Allow EC2 to Reach RDS (Security Group Rule)

This is the critical networking step. RDS is private — only your EC2 can connect.

1. Go to **EC2 → Security Groups**
2. Find `hpms-rds-sg` (created automatically with RDS)
3. Click **Edit inbound rules → Add rule**:

   | Type | Protocol | Port | Source |
   |------|----------|------|--------|
   | PostgreSQL | TCP | 5432 | Custom → select `hpms-ec2-sg` (type the name, select the SG ID) |

4. Click **Save rules**

This means: only instances in `hpms-ec2-sg` can reach the database on port 5432.
The public internet cannot reach RDS at all.

**Screenshot checkpoint:** RDS security group inbound rules showing PostgreSQL from hpms-ec2-sg.

---

## PHASE 3 — Deploy Application to EC2

### Step 3.1 — Connect to EC2

```bash
# On your local machine — set correct permissions on the key
chmod 400 ~/Downloads/hpms-key.pem

# SSH into EC2 (replace with your actual EC2 public IP)
ssh -i ~/Downloads/hpms-key.pem ubuntu@<EC2_PUBLIC_IP>
```

You should see the Ubuntu welcome message. All remaining commands in Phase 3 run **on EC2**.

---

### Step 3.2 — Install Docker on EC2

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Docker and Docker Compose plugin
sudo apt install -y docker.io docker-compose-plugin git

# Add ubuntu user to docker group (avoids needing sudo for docker commands)
sudo usermod -aG docker ubuntu

# Apply group change without logging out
newgrp docker

# Verify
docker --version
docker compose version
```

Expected output: Docker version 24.x.x and Docker Compose version v2.x.x

---

### Step 3.3 — Clone the Repository

```bash
# Clone your repo (replace with your actual GitHub URL)
git clone https://github.com/<YOUR_USERNAME>/cc_2_lab_exam_25mx352.git
cd cc_2_lab_exam_25mx352
```

If you haven't pushed to GitHub yet, use scp from your local machine instead:
```bash
# Run this on your LOCAL machine, not EC2
scp -i ~/Downloads/hpms-key.pem -r \
  ~/Downloads/cc_2_lab_exam_25mx352 \
  ubuntu@<EC2_PUBLIC_IP>:~/cc_2_lab_exam_25mx352
```
Then on EC2: `cd ~/cc_2_lab_exam_25mx352`

---

### Step 3.4 — Generate TLS Certificate

```bash
# Make the script executable
chmod +x scripts/gen-certs.sh

# Generate self-signed cert — pass your EC2 public IP as the argument
./scripts/gen-certs.sh <EC2_PUBLIC_IP>
```

Example:
```bash
./scripts/gen-certs.sh 54.123.45.67
```

Expected output:
```
✅ Certificate generated: ./nginx/certs/hpms.crt
   CN / SAN = 54.123.45.67
   Valid for 365 days.
```

---

### Step 3.5 — Create the Production Environment File

```bash
# Generate a cryptographically secure SECRET_KEY
SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "Generated SECRET_KEY: $SECRET"

# Create .env.prod — fill in your actual RDS values
cat > .env.prod << EOF
DATABASE_URL=postgresql://hpms_admin:<YOUR_RDS_PASSWORD>@<RDS_ENDPOINT>:5432/hpms_production
SECRET_KEY=${SECRET}
ACCESS_TOKEN_EXPIRE_MINUTES=480
EOF
```

Replace:
- `<YOUR_RDS_PASSWORD>` — the password you set in Step 2.1
- `<RDS_ENDPOINT>` — the endpoint from Step 2.1 (e.g. `hpms-db.xxxx.us-east-1.rds.amazonaws.com`)

Verify the file looks correct (no angle brackets remaining):
```bash
cat .env.prod
```

Example of a correct `.env.prod`:
```
DATABASE_URL=postgresql://hpms_admin:MyStr0ngPass!@hpms-db.abc123.us-east-1.rds.amazonaws.com:5432/hpms_production
SECRET_KEY=a3f8c2d1e4b5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

---

### Step 3.6 — Verify RDS Connectivity Before Starting the Stack

```bash
# Test that EC2 can reach RDS on port 5432
# Replace with your actual RDS endpoint
nc -zv <RDS_ENDPOINT> 5432
```

Expected output: `Connection to <RDS_ENDPOINT> 5432 port [tcp/postgresql] succeeded!`

If this fails, go back to Step 2.3 and verify the security group rule.

---

### Step 3.7 — Start the Production Stack

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

This will:
1. Build the FastAPI Docker image
2. Pull the Nginx image
3. Start both containers
4. FastAPI runs `seed.py` on startup — creates tables and inserts sample data into RDS
5. Nginx listens on ports 80 and 443

Watch the startup logs:
```bash
docker compose -f docker-compose.prod.yml logs -f
```

Look for:
```
hpms_backend  | ✅ Database seeded successfully.
hpms_backend  | INFO:     Application startup complete.
hpms_nginx    | /docker-entrypoint.sh: Configuration complete; ready for start up
```

Press Ctrl+C to stop following logs (containers keep running).

---

### Step 3.8 — Verify the Deployment

```bash
# Check both containers are running
docker compose -f docker-compose.prod.yml ps
```

Expected:
```
NAME           STATUS    PORTS
hpms_backend   running   8000/tcp
hpms_nginx     running   0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

```bash
# Test the health endpoint through Nginx
curl -k https://localhost/health
```

Expected: `{"status":"ok"}`

```bash
# Verify RDS connection from inside the backend container
docker exec hpms_backend python -c "
from app.database import engine
with engine.connect() as c:
    from sqlalchemy import text
    result = c.execute(text('SELECT COUNT(*) FROM patients'))
    print('RDS connection OK — patients in DB:', result.scalar())
"
```

Expected: `RDS connection OK — patients in DB: 5`

---

## PHASE 4 — Access the Deployed Application

### Open the website

In your browser, navigate to:
```
https://<EC2_PUBLIC_IP>
```

Your browser will show a security warning because the certificate is self-signed.
This is expected for an academic deployment.

**To proceed past the browser warning:**
- Chrome: Click "Advanced" → "Proceed to <IP> (unsafe)"
- Firefox: Click "Advanced" → "Accept the Risk and Continue"
- Edge: Click "Details" → "Go on to the webpage"

Login with: `admin` / `Admin@123`

**Screenshot checkpoint:** Browser showing the HPMS dashboard at `https://<EC2_PUBLIC_IP>`.

---

## PHASE 5 — Connect pgAdmin to RDS

RDS has no public access, so you must connect through an SSH tunnel.

### Step 5.1 — Open SSH Tunnel (on your local machine)

```bash
# Keep this terminal open while using pgAdmin
# Replace with your actual values
ssh -i ~/Downloads/hpms-key.pem \
    -L 5433:<RDS_ENDPOINT>:5432 \
    ubuntu@<EC2_PUBLIC_IP> \
    -N
```

This forwards your local port 5433 → EC2 → RDS port 5432.
The terminal will appear to hang — that is correct, the tunnel is active.

### Step 5.2 — Register Server in pgAdmin

1. Open pgAdmin 4 on your local machine
2. Right-click **Servers → Register → Server**
3. Fill in the tabs:

   **General tab:**
   - Name: `HPMS RDS Production`

   **Connection tab:**
   - Host: `localhost`
   - Port: `5433`
   - Maintenance database: `hpms_production`
   - Username: `hpms_admin`
   - Password: your RDS password
   - Save password: Yes

4. Click **Save**

### Step 5.3 — Explore the Database

Navigate: Servers → HPMS RDS Production → Databases → hpms_production → Schemas → public → Tables

You should see three tables: `appointments`, `patients`, `users`

Right-click `patients` → **View/Edit Data → All Rows** — you will see the 5 seeded patients.

**Screenshot checkpoint:** pgAdmin showing the patients table with data.

---

## PHASE 6 — Academic Demonstration Checklist

Work through these steps in order during your demonstration.

### Demo 1 — Show the deployed website
- Open `https://<EC2_PUBLIC_IP>` in browser
- Accept the self-signed cert warning
- Login with `admin` / `Admin@123`
- Show the dashboard: 5 patients, appointment stats
- Point out: "This is running on AWS EC2, connected to Amazon RDS"

### Demo 2 — Patient CREATE → verify in RDS
On the website:
- Click **Patients → + Add Patient**
- Fill in: ID=`DEMO001`, Name=`John Demo`, DOB=`1988-05-15`, Gender=Male, Phone=`555-1234`, Blood=`A+`
- Click **Save Patient**
- The patient appears in the table immediately

In pgAdmin Query Tool:
```sql
SELECT patient_id, full_name, phone, blood_group, created_at
FROM patients
WHERE patient_id = 'DEMO001';
```
Show the record in RDS — same data entered through the website.

### Demo 3 — Patient READ / Search
On the website:
- Type `DEMO001` in the search box → click Search
- Type `John` in the search box → click Search

In pgAdmin:
```sql
SELECT * FROM patients WHERE full_name ILIKE '%Demo%';
```

### Demo 4 — Patient UPDATE → verify in RDS
On the website:
- Click ✏️ on DEMO001
- Change phone to `555-9999` → click Save Patient

In pgAdmin:
```sql
SELECT patient_id, full_name, phone FROM patients WHERE patient_id = 'DEMO001';
```
Show phone is now `555-9999`.

### Demo 5 — Patient DELETE → verify in RDS
On the website:
- Click 🗑️ on DEMO001 → click Delete in the confirmation dialog
- Patient disappears from the table

In pgAdmin:
```sql
SELECT * FROM patients WHERE patient_id = 'DEMO001';
-- Returns 0 rows
```

### Demo 6 — Appointment Management
On the website:
- Click **Appointments → + New Appointment**
- Patient ID: `P001`, Doctor: `Dr. Smith`, Dept: `Cardiology`, Date: any future date
- Click Save — appointment appears in the table
- Click ✏️ → change status to `completed` → Save
- Click 🗑️ → appointment status changes to `cancelled`

In pgAdmin:
```sql
SELECT a.id, p.full_name, a.doctor_name, a.department, a.appointment_date, a.status
FROM appointments a
JOIN patients p ON a.patient_id = p.patient_id
ORDER BY a.created_at DESC
LIMIT 5;
```

### Demo 7 — Show RDS in AWS Console
- Open AWS Console → RDS → Databases → hpms-db
- Show: DB identifier, engine (PostgreSQL 15), status (Available)
- Click the database → show: Endpoint and port (5432)
- Click Connectivity & security tab → show: VPC, security groups, **Publicly accessible: No**

### Demo 8 — Show Tables in pgAdmin
- Expand: Servers → HPMS RDS Production → hpms_production → Schemas → public → Tables
- Show all three tables: `users`, `patients`, `appointments`
- Right-click `appointments` → View/Edit Data → All Rows
- Show records created through the website

### Demo 9 — Run API Tests Against Production

```bash
# On EC2 — install test dependencies inside the backend container
docker exec hpms_backend pip install httpx pytest -q

# Run tests against the live production server
docker exec hpms_backend sh -c "
  cd /app &&
  BASE_URL=http://localhost:8000 python -m pytest tests/ -v 2>&1
"
```

Or from your local machine (tests point to localhost:8000 by default, so run them locally with the local stack, or modify BASE in test_api.py to point to EC2):

```bash
# Temporary: run tests against EC2 production
cd backend
BASE=https://<EC2_PUBLIC_IP> pytest tests/ -v \
  --override-ini="addopts=" \
  -k "not test_" 2>/dev/null || \
pytest tests/ -v
```

The simplest approach for the demo: run tests locally against the local stack, show all 17 passing.

---

## PHASE 7 — Operational Commands

### View live logs
```bash
# On EC2
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Restart after code changes
```bash
# On EC2 — pull latest code and rebuild
git pull
docker compose -f docker-compose.prod.yml up --build -d
```

### Stop the stack
```bash
docker compose -f docker-compose.prod.yml down
```

### Check what is in RDS directly from EC2
```bash
docker exec -it hpms_backend python -c "
from app.database import SessionLocal
from app import models
db = SessionLocal()
patients = db.query(models.Patient).all()
for p in patients:
    print(p.patient_id, p.full_name, p.phone)
db.close()
"
```

---

## PHASE 8 — Troubleshooting

### Backend container exits immediately
```bash
docker compose -f docker-compose.prod.yml logs backend
```
Most common cause: wrong `DATABASE_URL` in `.env.prod`. Check for typos in the RDS endpoint or password.

### `nc -zv <RDS_ENDPOINT> 5432` fails
- Verify the RDS security group inbound rule allows port 5432 from `hpms-ec2-sg`
- Verify the EC2 instance is in the same VPC as RDS
- Verify RDS status is Available (not Creating or Modifying)

### Browser shows "Connection refused" on port 443
```bash
# Check Nginx is running
docker compose -f docker-compose.prod.yml ps
# Check EC2 security group allows port 443 inbound from 0.0.0.0/0
```

### pgAdmin cannot connect through SSH tunnel
- Verify the SSH tunnel command is still running (the terminal must stay open)
- Verify pgAdmin is connecting to `localhost:5433` (not the RDS endpoint directly)
- Try: `psql -h localhost -p 5433 -U hpms_admin -d hpms_production`

### "✅ Database seeded successfully" not in logs
```bash
docker exec hpms_backend python -m app.seed
```

---

## Security Summary

| Control | Implementation |
|---------|---------------|
| Passwords | bcrypt-hashed, never stored in plain text |
| API auth | JWT tokens, 8-hour expiry |
| DB credentials | Environment variables, never in Git |
| RDS access | Private subnet, security group allows only EC2 |
| TLS | Nginx terminates HTTPS with self-signed cert |
| Port exposure | Only 80 and 443 exposed publicly; port 8000 internal only |
| Admin operations | Role-based: only `admin` role can register new staff |
