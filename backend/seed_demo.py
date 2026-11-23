"""Fill a LOCAL development database with demo accounts and bookings in every workflow state.

    python seed_demo.py --reset

For local demos and screenshots only: the demo accounts share a documented password, so never run this against a real
deployment. It goes through the same workflow code as the app, so every booking has a genuine history and notifications.

    --reset   first empty bookings, history, notifications and blocks (users are kept)
"""
import os
import sys
from datetime import date, timedelta

from auth import hash_password
from db import get_db
from workflow import PENDING, apply_transition, record_event, release_slot

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "demo-password-1")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@unispace.test")
STUDENTS = [("Aisha Khan", "aisha@example.com"), ("Bilal Ahmed", "bilal@example.com"),
            ("Sara Malik", "sara@example.com"), ("Tariq Hussain", "tariq@example.com")]
COLUMNS = ("id", "username", "resource", "date", "time_slot", "status")


def weekday(offset):
    """The offset-th weekday after today (1 = the next weekday), as an ISO date."""
    day, seen = date.today(), 0
    while seen < offset:
        day += timedelta(days=1)
        if day.weekday() < 5:
            seen += 1
    return day.isoformat()


def main():
    reset = "--reset" in sys.argv
    db = get_db()
    cursor = db.cursor()

    if reset:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in ("booking_events", "notifications", "blocked_slots", "bookings"):
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    for name, email in [("Admin", ADMIN_EMAIL)] + STUDENTS:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if not cursor.fetchone():
            role = "admin" if name == "Admin" else "student"
            cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                           (name, email, hash_password(DEMO_PASSWORD), role))
    db.commit()

    def request(username, resource, day, slot):
        cursor.execute("INSERT INTO bookings (username, resource, booking_date, time_slot, status) VALUES (%s, %s, %s, %s, %s)",
                       (username, resource, day, slot, PENDING))
        booking_id = cursor.lastrowid
        record_event(cursor, booking_id, None, PENDING, username)
        return dict(zip(COLUMNS, (booking_id, username, resource, day, slot, PENDING)))

    def move(booking, status, actor, note=None):
        apply_transition(cursor, booking, status, actor, note)
        booking["status"] = status

    d1, d2, d3, d4 = weekday(1), weekday(2), weekday(3), weekday(4)

    # Two students ask for the same lab slot; the administrator reviews and approves one, the other is declined automatically
    aisha_lab = request("Aisha Khan", "Lab", d1, "10-11")
    request("Bilal Ahmed", "Lab", d1, "10-11")
    move(aisha_lab, "Under Review", "Admin")
    move(aisha_lab, "Approved", "Admin")

    # One request still in review, a few new ones, one rejected with a reason, one cancelled by its owner
    in_review = request("Aisha Khan", "Conference Room", d2, "2-3")
    move(in_review, "Under Review", "Admin")
    request("Aisha Khan", "Study Room", d3, "9-10")
    request("Sara Malik", "Auditorium", d2, "3-4")
    request("Sara Malik", "Lab", d3, "1-2")
    request("Tariq Hussain", "Study Room", d2, "4-5")
    rejected = request("Bilal Ahmed", "Study Room", d2, "11-12")
    move(rejected, "Rejected", "Admin", "Reserved for the department exam")
    cancelled = request("Tariq Hussain", "Conference Room", d3, "4-5")
    move(cancelled, "Cancelled", "Tariq Hussain", "Plans changed")

    # A maintenance block on a day that already has a request, so the block's effect is visible
    cursor.execute("INSERT INTO blocked_slots (resource, blocked_date, time_slot) VALUES ('Auditorium', %s, '9-10')", (d4,))
    request("Sara Malik", "Auditorium", d4, "9-10")
    release_slot(cursor, "Auditorium", d4, "9-10")

    db.commit()
    cursor.close()
    db.close()
    print(f"Demo data loaded. Admin: {ADMIN_EMAIL}. Students: " + ", ".join(e for _, e in STUDENTS) + f". Password for all: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
