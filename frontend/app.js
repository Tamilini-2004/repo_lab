/* ── Config ──────────────────────────────────────────────────────────────── */
// Empty string = same origin (works for both local Docker and EC2 production).
// Set window.API_BASE before this script only if backend is on a different host.
const API = window.API_BASE || "";

/* ── State ───────────────────────────────────────────────────────────────── */
let token = localStorage.getItem("hpms_token") || null;
let currentUser = null;
let editingPatientId = null;   // patient_id string when editing
let editingApptId = null;      // appointment id (int) when editing
let pendingDeleteFn = null;    // function to call on confirm delete

/* ── API helper ──────────────────────────────────────────────────────────── */
async function api(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

/* ── Auth ────────────────────────────────────────────────────────────────── */
document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("loginError");
  errEl.classList.add("hidden");
  const form = new URLSearchParams();
  form.append("username", document.getElementById("loginUsername").value.trim());
  form.append("password", document.getElementById("loginPassword").value);
  try {
    const res = await fetch(`${API}/api/auth/login`, { method: "POST", body: form });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Login failed");
    token = data.access_token;
    localStorage.setItem("hpms_token", token);
    await initApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  }
});

document.getElementById("logoutBtn").addEventListener("click", () => {
  token = null;
  currentUser = null;
  localStorage.removeItem("hpms_token");
  document.getElementById("app").classList.add("hidden");
  document.getElementById("loginScreen").classList.remove("hidden");
});

async function initApp() {
  try {
    currentUser = await api("GET", "/api/auth/me");
  } catch {
    token = null;
    localStorage.removeItem("hpms_token");
    return;
  }
  document.getElementById("sidebarUserName").textContent = currentUser.full_name;
  document.getElementById("sidebarUserRole").textContent = currentUser.role;
  if (currentUser.role !== "admin") document.getElementById("staffNavItem").classList.add("hidden");
  document.getElementById("loginScreen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");
  navigateTo("dashboard");
}

/* ── Navigation ──────────────────────────────────────────────────────────── */
document.querySelectorAll(".nav-item").forEach((el) => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    navigateTo(el.dataset.page);
  });
});

function navigateTo(page) {
  document.querySelectorAll(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.page === page));
  document.querySelectorAll(".page").forEach((el) => el.classList.toggle("active", el.id === `page-${page}`));
  if (page === "dashboard") loadDashboard();
  if (page === "patients") loadPatients();
  if (page === "appointments") loadAppointments();
}

/* ── Dashboard ───────────────────────────────────────────────────────────── */
async function loadDashboard() {
  const [patients, appointments] = await Promise.all([
    api("GET", "/api/patients/?limit=5"),
    api("GET", "/api/appointments/?limit=100"),
  ]);

  document.getElementById("statPatients").textContent = patients.length >= 5 ? "5+" : patients.length;
  const scheduled = appointments.filter((a) => a.status === "scheduled").length;
  const completed = appointments.filter((a) => a.status === "completed").length;
  const cancelled = appointments.filter((a) => a.status === "cancelled").length;
  document.getElementById("statScheduled").textContent = scheduled;
  document.getElementById("statCompleted").textContent = completed;
  document.getElementById("statCancelled").textContent = cancelled;

  document.getElementById("recentPatients").innerHTML = patients
    .slice(0, 5)
    .map((p) => `<tr><td>${p.patient_id}</td><td>${p.full_name}</td><td>${p.blood_group || "—"}</td><td>${p.phone}</td></tr>`)
    .join("");

  document.getElementById("upcomingAppointments").innerHTML = appointments
    .filter((a) => a.status === "scheduled")
    .slice(0, 5)
    .map((a) => `<tr><td>${a.patient_id}</td><td>${a.doctor_name}</td><td>${fmtDate(a.appointment_date)}</td><td>${badge(a.status)}</td></tr>`)
    .join("");
}

/* ── Patients ────────────────────────────────────────────────────────────── */
async function loadPatients(search = "") {
  const url = search ? `/api/patients/?search=${encodeURIComponent(search)}` : "/api/patients/";
  const patients = await api("GET", url);
  document.getElementById("patientsTbody").innerHTML = patients.map((p) => `
    <tr>
      <td><strong>${p.patient_id}</strong></td>
      <td>${p.full_name}</td>
      <td>${p.date_of_birth}</td>
      <td style="text-transform:capitalize">${p.gender}</td>
      <td>${p.blood_group || "—"}</td>
      <td>${p.phone}</td>
      <td>
        <button class="btn-icon" title="Edit" onclick="openEditPatient('${p.patient_id}')">✏️</button>
        <button class="btn-icon" title="Delete" onclick="confirmDelete('patient','${p.patient_id}','${p.full_name}')">🗑️</button>
      </td>
    </tr>`).join("") || `<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No patients found</td></tr>`;
}

document.getElementById("patientSearchBtn").addEventListener("click", () => {
  loadPatients(document.getElementById("patientSearch").value.trim());
});
document.getElementById("patientSearch").addEventListener("keydown", (e) => {
  if (e.key === "Enter") loadPatients(document.getElementById("patientSearch").value.trim());
});

document.getElementById("addPatientBtn").addEventListener("click", () => openPatientModal());

function openPatientModal(patient = null) {
  editingPatientId = patient ? patient.patient_id : null;
  document.getElementById("patientModalTitle").textContent = patient ? "Edit Patient" : "Add Patient";
  document.getElementById("fPatientId").value = patient?.patient_id || "";
  document.getElementById("fPatientId").disabled = !!patient;
  document.getElementById("fFullName").value = patient?.full_name || "";
  document.getElementById("fDob").value = patient?.date_of_birth || "";
  document.getElementById("fGender").value = patient?.gender || "";
  document.getElementById("fPhone").value = patient?.phone || "";
  document.getElementById("fEmail").value = patient?.email || "";
  document.getElementById("fBlood").value = patient?.blood_group || "";
  document.getElementById("fAddress").value = patient?.address || "";
  document.getElementById("patientFormError").classList.add("hidden");
  document.getElementById("patientModal").classList.remove("hidden");
}

async function openEditPatient(patientId) {
  const patient = await api("GET", `/api/patients/${patientId}`);
  openPatientModal(patient);
}

document.getElementById("patientForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("patientFormError");
  errEl.classList.add("hidden");
  const payload = {
    patient_id: document.getElementById("fPatientId").value.trim(),
    full_name: document.getElementById("fFullName").value.trim(),
    date_of_birth: document.getElementById("fDob").value,
    gender: document.getElementById("fGender").value,
    phone: document.getElementById("fPhone").value.trim(),
    email: document.getElementById("fEmail").value.trim() || null,
    blood_group: document.getElementById("fBlood").value || null,
    address: document.getElementById("fAddress").value.trim() || null,
  };
  try {
    if (editingPatientId) {
      const { patient_id, ...updatePayload } = payload;
      await api("PUT", `/api/patients/${editingPatientId}`, updatePayload);
    } else {
      await api("POST", "/api/patients/", payload);
    }
    closeModal("patientModal");
    loadPatients();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  }
});

/* ── Appointments ────────────────────────────────────────────────────────── */
async function loadAppointments(patientId = "", status = "") {
  let url = "/api/appointments/?limit=100";
  if (patientId) url += `&patient_id=${encodeURIComponent(patientId)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  const appts = await api("GET", url);
  document.getElementById("apptTbody").innerHTML = appts.map((a) => `
    <tr>
      <td>${a.id}</td>
      <td>${a.patient_id}</td>
      <td>${a.doctor_name}</td>
      <td>${a.department}</td>
      <td>${fmtDate(a.appointment_date)}</td>
      <td>${badge(a.status)}</td>
      <td>
        <button class="btn-icon" title="Edit" onclick="openEditAppt(${a.id})">✏️</button>
        <button class="btn-icon" title="Cancel" onclick="confirmDelete('appt',${a.id},'appointment #${a.id}')">🗑️</button>
      </td>
    </tr>`).join("") || `<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">No appointments found</td></tr>`;
}

document.getElementById("apptFilterBtn").addEventListener("click", () => {
  loadAppointments(
    document.getElementById("apptPatientFilter").value.trim(),
    document.getElementById("apptStatusFilter").value
  );
});

document.getElementById("addApptBtn").addEventListener("click", () => openApptModal());
document.getElementById("addStaffBtn").addEventListener("click", () => navigateTo("staff"));

function openApptModal(appt = null) {
  editingApptId = appt ? appt.id : null;
  document.getElementById("apptModalTitle").textContent = appt ? "Edit Appointment" : "New Appointment";
  document.getElementById("aPatientId").value = appt?.patient_id || "";
  document.getElementById("aDoctorName").value = appt?.doctor_name || "";
  document.getElementById("aDepartment").value = appt?.department || "";
  document.getElementById("aDate").value = appt ? appt.appointment_date.slice(0, 16) : "";
  document.getElementById("aStatus").value = appt?.status || "scheduled";
  document.getElementById("aReason").value = appt?.reason || "";
  document.getElementById("aNotes").value = appt?.notes || "";
  document.getElementById("apptFormError").classList.add("hidden");
  document.getElementById("apptModal").classList.remove("hidden");
}

async function openEditAppt(apptId) {
  const appt = await api("GET", `/api/appointments/${apptId}`);
  openApptModal(appt);
}

document.getElementById("apptForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("apptFormError");
  errEl.classList.add("hidden");
  const payload = {
    patient_id: document.getElementById("aPatientId").value.trim(),
    doctor_name: document.getElementById("aDoctorName").value.trim(),
    department: document.getElementById("aDepartment").value.trim(),
    appointment_date: new Date(document.getElementById("aDate").value).toISOString(),
    status: document.getElementById("aStatus").value,
    reason: document.getElementById("aReason").value.trim() || null,
    notes: document.getElementById("aNotes").value.trim() || null,
  };
  try {
    if (editingApptId) {
      const { patient_id, ...updatePayload } = payload;
      await api("PUT", `/api/appointments/${editingApptId}`, updatePayload);
    } else {
      await api("POST", "/api/appointments/", payload);
    }
    closeModal("apptModal");
    loadAppointments();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  }
});

/* ── Staff ───────────────────────────────────────────────────────────────── */
document.getElementById("addStaffForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msgEl = document.getElementById("staffMsg");
  msgEl.className = "hidden";
  try {
    await api("POST", "/api/auth/register", {
      username: document.getElementById("staffUsername").value.trim(),
      full_name: document.getElementById("staffFullName").value.trim(),
      password: document.getElementById("staffPassword").value,
      role: document.getElementById("staffRole").value,
    });
    msgEl.textContent = "Staff account created successfully.";
    msgEl.className = "success-msg";
    e.target.reset();
  } catch (err) {
    msgEl.textContent = err.message;
    msgEl.className = "error-msg";
  }
});

/* ── Confirm Delete ──────────────────────────────────────────────────────── */
function confirmDelete(type, id, label) {
  document.getElementById("confirmMsg").textContent = `Delete ${label}? This cannot be undone.`;
  pendingDeleteFn = async () => {
    if (type === "patient") {
      await api("DELETE", `/api/patients/${id}`);
      loadPatients();
    } else {
      await api("DELETE", `/api/appointments/${id}`);
      loadAppointments();
    }
    closeModal("confirmModal");
  };
  document.getElementById("confirmModal").classList.remove("hidden");
}

document.getElementById("confirmDeleteBtn").addEventListener("click", async () => {
  if (pendingDeleteFn) await pendingDeleteFn();
});

/* ── Modal helpers ───────────────────────────────────────────────────────── */
function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}
document.querySelectorAll("[data-modal]").forEach((el) => {
  el.addEventListener("click", () => closeModal(el.dataset.modal));
});
document.querySelectorAll(".modal").forEach((modal) => {
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal(modal.id);
  });
});

/* ── Utilities ───────────────────────────────────────────────────────────── */
function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

function badge(status) {
  return `<span class="badge badge-${status}">${status}</span>`;
}

/* ── Boot ────────────────────────────────────────────────────────────────── */
if (token) initApp();
