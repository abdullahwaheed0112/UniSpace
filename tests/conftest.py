"""Shared test setup.

The tests run against a throwaway MySQL database called `unispace_test`. It is created from database/schema.sql at the
start of the run and dropped at the end, so your real `unispace` database is never touched.

Connection settings come from the same DB_* environment variables as the app (or the .env file); only DB_NAME is forced.
If MySQL cannot be reached, the database tests are skipped instead of failing.
"""
import os
import re
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import mysql.connector
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DB_NAME"] = "unispace_test"  # must be set before config is imported

import config  # noqa: E402
from auth import hash_password  # noqa: E402

TEST_DB = "unispace_test"
ADMIN_EMAIL = "admin@unispace.test"
ADMIN_PASSWORD = "Correct-Horse-9"
STUDENT_PASSWORD = "longenough1"


def _admin_connection(database=None):
    return mysql.connector.connect(host=config.DB_HOST, port=config.DB_PORT, user=config.DB_USER,
                                   password=config.DB_PASSWORD, database=database)


def _schema_statements():
    """database/schema.sql without its CREATE DATABASE / USE lines, split into single statements."""
    text = (ROOT / "database" / "schema.sql").read_text(encoding="utf-8")
    text = re.sub(r"--[^\n]*", "", text)  # drop comments
    statements = [s.strip() for s in text.split(";") if s.strip()]
    return [s for s in statements if not s.upper().startswith(("CREATE DATABASE", "USE "))]


@pytest.fixture(scope="session")
def database():
    try:
        server = _admin_connection()
    except mysql.connector.Error as err:
        pytest.skip(f"MySQL is not reachable ({err.msg if hasattr(err, 'msg') else err}); set DB_HOST/DB_PORT/DB_USER/DB_PASSWORD")
    cursor = server.cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cursor.execute(f"CREATE DATABASE {TEST_DB}")
    cursor.execute(f"USE {TEST_DB}")
    for statement in _schema_statements():
        cursor.execute(statement)
    cursor.execute("INSERT INTO users (username, email, password, role) VALUES ('Admin', %s, %s, 'admin')",
                   (ADMIN_EMAIL, hash_password(ADMIN_PASSWORD)))
    server.commit()
    yield
    cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    server.commit()
    cursor.close()
    server.close()


@pytest.fixture(autouse=False)
def clean(database):
    """Empty the per-test tables (users stay: the admin is created once)."""
    conn = _admin_connection(TEST_DB)
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    for table in ("booking_events", "notifications", "blocked_slots", "bookings"):
        cursor.execute(f"TRUNCATE TABLE {table}")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()


@pytest.fixture
def client(clean):
    import app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _login(client, email, password):
    response = client.post("/signin", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_json()
    return {"Authorization": "Bearer " + response.get_json()["token"]}


@pytest.fixture
def admin(client):
    return _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def make_student(client):
    """Create a fresh student and return their auth headers."""

    def _make(name=None):
        name = name or "stu" + uuid.uuid4().hex[:8]
        response = client.post("/signup", json={"username": name, "email": f"{name}@example.com", "password": STUDENT_PASSWORD})
        assert response.status_code == 201, response.get_json()
        headers = _login(client, f"{name}@example.com", STUDENT_PASSWORD)
        headers["X-Test-Username"] = name  # not sent to the app logic; just handy in assertions
        return headers

    return _make


def next_weekday(days_ahead=1):
    """A weekday inside the booking window, as an ISO date string."""
    day = date.today() + timedelta(days=days_ahead)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.isoformat()


@pytest.fixture
def book(client):
    def _book(headers, resource="Lab", day=None, slot="10-11"):
        return client.post("/bookings", json={"resource": resource, "date": day or next_weekday(), "timeSlot": slot}, headers=headers)

    return _book


@pytest.fixture
def move(client):
    def _move(headers, booking_id, status, note=None):
        body = {"status": status}
        if note is not None:
            body["note"] = note
        return client.put(f"/bookings/{booking_id}/status", json=body, headers=headers)

    return _move


@pytest.fixture
def booking_ids(client, admin):
    """Map username -> booking id for one slot."""

    def _ids(resource="Lab", day=None, slot="10-11"):
        day = day or next_weekday()
        rows = client.get("/bookings", headers=admin).get_json()
        return {b["username"]: b["id"] for b in rows if (b["resource"], b["date"], b["timeSlot"]) == (resource, day, slot)}

    return _ids
