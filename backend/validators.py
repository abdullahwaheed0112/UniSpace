"""Input checks. Every function returns an error message (str) when the input is bad, or None when it is fine.

The server never trusts the browser: the same rules the forms apply are enforced here.
"""
import re
from datetime import date, datetime, timedelta

# The things a booking can refer to. Kept in one place so the API, the schema notes and the UI agree.
RESOURCES = ("Conference Room", "Study Room", "Lab", "Auditorium")

# slot code -> start hour (24 h clock). Hourly slots, 9 AM to 5 PM with a lunch break.
TIME_SLOTS = {"9-10": 9, "10-11": 10, "11-12": 11, "1-2": 13, "2-3": 14, "3-4": 15, "4-5": 16}

BOOKING_WINDOW_DAYS = 7      # a student can book from today up to this many days ahead
BLOCK_WINDOW_DAYS = 90       # an admin can block slots up to this many days ahead

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_. -]{2,29}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def parse_date(value):
    """'2026-11-26' -> date, or None if it is not a real ISO date."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def validate_signup(username, email, password):
    if not USERNAME_RE.match(username or ""):
        return "Username must be 3 to 30 characters: letters, numbers, spaces, dots, dashes or underscores."
    if len(email or "") > 100 or not EMAIL_RE.match(email or ""):
        return "Please enter a valid email address."
    if not isinstance(password, str) or not (MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH):
        return f"Password must be {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters."
    return None


def validate_slot(resource, time_slot):
    if resource not in RESOURCES:
        return "Unknown resource."
    if time_slot not in TIME_SLOTS:
        return "Unknown time slot."
    return None


def validate_booking(resource, booking_date, time_slot, now=None):
    """A student's booking request: real resource and slot, a weekday inside the booking window, not in the past."""
    error = validate_slot(resource, time_slot)
    if error:
        return error
    day = parse_date(booking_date)
    if day is None:
        return "Please choose a valid date."
    now = now or datetime.now()
    today = now.date()
    if day < today or day > today + timedelta(days=BOOKING_WINDOW_DAYS):
        return f"Bookings can be made from today up to {BOOKING_WINDOW_DAYS} days ahead."
    if day.weekday() >= 5:
        return "Resources can only be booked Monday to Friday."
    if datetime.combine(day, datetime.min.time()).replace(hour=TIME_SLOTS[time_slot]) <= now:
        return "That time slot has already started."
    return None


def validate_block(resource, block_date, time_slot, today=None):
    """An admin's maintenance block: real resource and slot, today or later, within the block window."""
    error = validate_slot(resource, time_slot)
    if error:
        return error
    day = parse_date(block_date)
    if day is None:
        return "Please choose a valid date."
    today = today or date.today()
    if day < today or day > today + timedelta(days=BLOCK_WINDOW_DAYS):
        return f"Slots can be blocked from today up to {BLOCK_WINDOW_DAYS} days ahead."
    return None
