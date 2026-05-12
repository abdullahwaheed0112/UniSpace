# UniSpace+ 🏛️

> **A full-stack university resource booking platform** — allowing students to reserve campus spaces (conference rooms, labs, study rooms, and auditoriums) and giving admins complete control over scheduling.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)
- [API Reference](#-api-reference)
- [Pages & UI](#-pages--ui)
- [Setup & Installation](#-setup--installation)
- [Default Credentials](#-default-credentials)
- [Known Limitations & Notes](#-known-limitations--notes)

---

## 🌐 Overview

**UniSpace+** is a campus resource management web application built for universities. It allows students to browse available rooms, make booking requests, and track their booking status — while admins can approve/reject requests, block time slots for maintenance, view reports, and receive automatic system notifications.

The app follows a simple **frontend → REST API → MySQL** architecture with no framework on the frontend (vanilla HTML/CSS/JS + Bootstrap) and a lightweight **Flask** backend.

---

## ✨ Features

### 👨‍🎓 Student Features
- **Sign Up / Sign In** — Account registration and authentication with role-based access
- **Browse Resources** — View real-time availability for Conference Rooms, Study Rooms, Labs, and Auditoriums for the next 7 days
- **Make a Booking** — Book any available time slot with a simple form; automatically blocked slots are prevented
- **My Bookings** — View all personal bookings with current status (Pending / Approved / Rejected)
- **Notifications** — Receive in-app notifications when booking status changes (Approved/Rejected)

### 🛡️ Admin Features
- **Admin Dashboard** — Central panel for all admin operations
- **Approve / Reject Bookings** — Review all student booking requests and action them
- **Block Time Slots** — Block specific resource + date + time slot combinations for maintenance; auto-rejects any pending bookings in that slot and notifies students
- **Unblock Slots** — Remove existing blocks from slots
- **Reports** — View statistics: total bookings, approved, rejected, and pending counts
- **Role-based Navigation** — Navbar dynamically adapts based on whether user is admin or student

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript, Bootstrap 5.3, Font Awesome 6 |
| **Backend** | Python 3, Flask, Flask-CORS |
| **Database** | MySQL |
| **DB Connector** | `mysql-connector-python` |
| **Dev Server** | VS Code Live Server (frontend), Flask dev server (backend) |

---

## 📁 Project Structure

```
UNISPACE-/
├── backend/
│   └── app.py              # Flask REST API — all routes
├── database/
│   └── schema.sql          # MySQL schema + seed data
├── frontend/
│   ├── index.html          # Home / landing page
│   ├── index.css           # Home page styles
│   ├── signin.html         # Sign in page
│   ├── signup.html         # Sign up page
│   ├── signup.js           # Sign up form logic
│   ├── booking.html        # Booking form page
│   ├── mybookings.html     # Student's bookings list
│   ├── mybookings.css      # My Bookings styles
│   ├── resources.html      # Availability table (7-day view)
│   ├── resources.css       # Resources page styles
│   ├── dashboard.html      # Admin dashboard
│   ├── dashboard.css       # Admin dashboard styles
│   ├── navbar.html         # Shared navbar HTML template
│   ├── loadNavbar.js       # Dynamically injects navbar + role-based links
│   ├── script.js           # Shared JS: sign in, booking, my bookings logic
│   └── style.css           # Global shared styles
└── images/
    └── pawel-czerwinski-*.jpg   # Hero background image
```

---

## 🗄️ Database Schema

The app uses a single MySQL database named `unispace` with **4 tables**:

### `users`
| Column | Type | Notes |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primary key |
| `username` | VARCHAR(50) | Display name |
| `email` | VARCHAR(100) | Login email |
| `password` | VARCHAR(100) | Plain text (see notes) |
| `role` | VARCHAR(20) | `'student'` or `'admin'` (default: `'student'`) |

### `bookings`
| Column | Type | Notes |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primary key |
| `username` | VARCHAR(50) | Booking owner |
| `resource` | VARCHAR(50) | e.g. `Conference Room` |
| `booking_date` | DATE | |
| `time_slot` | VARCHAR(20) | e.g. `9-10` |
| `status` | VARCHAR(20) | `Pending` / `Approved` / `Rejected` |
| `created_at` | TIMESTAMP | Auto |

### `blocked_slots`
| Column | Type | Notes |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primary key |
| `resource` | VARCHAR(50) | |
| `blocked_date` | DATE | |
| `time_slot` | VARCHAR(20) | |
| `created_at` | TIMESTAMP | Auto |

### `notifications`
| Column | Type | Notes |
|---|---|---|
| `id` | INT AUTO_INCREMENT | Primary key |
| `username` | VARCHAR(50) | Recipient |
| `message` | VARCHAR(255) | Notification text |
| `is_read` | BOOLEAN | Default: `FALSE` |
| `created_at` | TIMESTAMP | Auto |

---

## 🔌 API Reference

Base URL: `http://localhost:5000`

### Auth

| Method | Route | Description | Body |
|---|---|---|---|
| `POST` | `/signup` | Register new user | `{ username, email, password }` |
| `POST` | `/signin` | Sign in | `{ email, password }` → returns `{ username, role }` |

### Bookings

| Method | Route | Description |
|---|---|---|
| `POST` | `/bookings` | Create booking — `{ username, resource, date, timeSlot }` |
| `GET` | `/bookings` | Get all bookings (admin) or filter by `?username=` (student) |
| `PUT` | `/bookings/<id>/status` | Update booking status — `{ status: "Approved"/"Rejected" }` (also triggers notification) |

### Blocked Slots

| Method | Route | Description |
|---|---|---|
| `POST` | `/blocked_slots` | Block a slot — `{ resource, date, time }` (auto-rejects pending bookings + notifies) |
| `GET` | `/blocked_slots` | List all blocked slots |
| `DELETE` | `/blocked_slots/<id>` | Unblock a slot |

### Notifications

| Method | Route | Description |
|---|---|---|
| `GET` | `/notifications?username=` | Get all notifications for a user |
| `PUT` | `/notifications/read` | Mark all as read — `{ username }` |

---

## 🖥️ Pages & UI

### 🏠 Home (`index.html`)
The landing page features a full-screen blurred background hero with animated fade-in elements. Includes a feature highlights section (Instant Booking, Real-Time Availability, Admin Control) and call-to-action buttons. Navigation adapts based on login state.

### 🔐 Sign In / Sign Up (`signin.html`, `signup.html`)
Clean authentication forms. On sign-in, `username` and `role` are persisted to `localStorage` and used for role-based routing throughout the app.

### 📅 Resources (`resources.html`)
Select a resource from the dropdown; a 7-day availability table is rendered dynamically. Each cell shows:
- 🟢 **Free** — available to book
- 🔴 **Booked** — already reserved
- 🟡 **Blocked by Admin** — maintenance block

### 📝 Booking (`booking.html`)
A glass-card booking form where students pick resource, date, and time slot. Time slots that have already passed in the current day are automatically hidden. Blocked slots are rejected server-side with a user-friendly error message.

### 📋 My Bookings (`mybookings.html`)
Displays all bookings for the logged-in student as cards with color-coded status badges (Pending / Approved / Rejected). Includes a notification bell that shows unread notifications.

### 🛡️ Admin Dashboard (`dashboard.html`)
Split into two panels:
1. **Booking Requests** — scrollable card list with Approve/Reject buttons per booking
2. **Admin Actions** (tabbed):
   - *Block Time Slots* — form to block a resource/date/time, plus a live list of all current blocks with unblock buttons
   - *View Reports* — stat cards showing Total, Approved, Rejected, and Pending booking counts

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.8+
- MySQL Server
- VS Code with the **Live Server** extension (for frontend)
- pip

### 1. Clone / Extract the Project

```bash
unzip Unispace_.zip
cd i242582_i242510_i242567/UNISPACE-
```

### 2. Set Up the Database

Open MySQL and run the schema file:

```bash
mysql -u root -p < database/schema.sql
```

This creates the `unispace` database, all 4 tables, and seeds the default admin account.

### 3. Install Python Dependencies

```bash
pip install flask flask-cors mysql-connector-python
```

### 4. Configure the Database Connection

In `backend/app.py`, update the MySQL connection settings if your credentials differ:

```python
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="123456",   # ← change this
    database="unispace"
)
```

> ⚠️ The DB connection is hardcoded in every route. Consider extracting it to a config or using environment variables for production.

### 5. Start the Backend

```bash
cd backend
python app.py
```

Flask will start at `http://localhost:5000`.

### 6. Start the Frontend

Open the `frontend/` folder in VS Code and click **Go Live** (Live Server). The app will open at `http://127.0.0.1:5500/frontend/index.html` (port may vary).

> Make sure the frontend's fetch calls point to `http://localhost:5000` — this is already configured in `script.js`.

---

## 🔑 Default Credentials

A default admin user is seeded by `schema.sql`:

| Field | Value |
|---|---|
| Email | `admin@unispace.com` |
| Password | `admin123` |
| Role | `admin` |

Students can self-register via the Sign Up page. New accounts default to the `student` role.

---

## ⚠️ Known Limitations & Notes

- **Passwords are stored in plain text.** This is not safe for production. Use hashing (e.g. `bcrypt`) before deploying.
- **No session/token authentication.** Login state is stored in `localStorage` with no server-side validation — any user can manually set their role in the browser.
- **Hardcoded DB credentials** in every route in `app.py`. Use a `.env` file and `python-dotenv` for a real deployment.
- **Available resources are hardcoded** in both the frontend dropdowns and backend logic. Extending to support dynamic resources would require schema changes.
- **Time slots are fixed** to 6 hourly slots between 9 AM–4 PM (Mon–Fri only, past slots are hidden client-side).
- **No duplicate booking prevention** — the same student could theoretically book the same slot twice if not checked.
- The `username` foreign key constraint on `bookings` was intentionally omitted (noted in `schema.sql`) to simplify migration from a previous localStorage-based version.

---

## 👥 Contributors

Built as a university group project.
IDs: `i242582`, `i242510`, `i242567`
