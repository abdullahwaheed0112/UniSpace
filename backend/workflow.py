"""The booking approval workflow: which status changes are allowed, who may make them, and what happens next.

    Pending ──► Under Review ──► Approved ──► Cancelled
       │              │
       ├─► Rejected ◄─┘            (a reason is required)
       └─► Cancelled               (the owner may cancel; an admin must give a reason)

Rules, in plain words:
- A booking cannot be approved before an admin has taken it into review.
- Approving a booking automatically rejects the other open requests for the same slot.
- Rejected and Cancelled are final.
- Every change is written to the booking_events table, so a booking's history is always visible.
"""
from datetime import datetime

from validators import SLOT_LABELS

PENDING, REVIEW, APPROVED, REJECTED, CANCELLED = "Pending", "Under Review", "Approved", "Rejected", "Cancelled"
STATUSES = (PENDING, REVIEW, APPROVED, REJECTED, CANCELLED)
OPEN_STATUSES = (PENDING, REVIEW)  # still waiting for a decision

# current status -> {new status: the roles that may do it}.  "owner" = the student who made the booking.
TRANSITIONS = {
    PENDING: {REVIEW: {"admin"}, REJECTED: {"admin"}, CANCELLED: {"owner", "admin"}},
    REVIEW: {APPROVED: {"admin"}, REJECTED: {"admin"}, CANCELLED: {"owner", "admin"}},
    APPROVED: {CANCELLED: {"owner", "admin"}},
}

MAX_NOTE_LENGTH = 200


def roles_for(user, booking):
    """Which roles this user holds for this booking: a subset of {"owner", "admin"}."""
    roles = set()
    if user["role"] == "admin":
        roles.add("admin")
    if user["username"] == booking["username"]:
        roles.add("owner")
    return roles


def check_transition(current, target, roles, note):
    """Return None if the change is allowed, otherwise (http_status, message)."""
    allowed = TRANSITIONS.get(current)
    if not allowed or target not in allowed:
        if current in (REJECTED, CANCELLED):
            return 409, f"This booking is already {current.lower()} and cannot change."
        return 409, f"A {current} booking cannot be changed to {target}."
    if not (allowed[target] & roles):
        return 403, "You are not allowed to make that change."
    admin_decision = "admin" in roles and "owner" not in roles
    if (target == REJECTED or (target == CANCELLED and admin_decision)) and not (note or "").strip():
        return 400, "Please give a reason."
    if note and len(note.strip()) > MAX_NOTE_LENGTH:
        return 400, f"Keep the reason under {MAX_NOTE_LENGTH} characters."
    return None


def _friendly_date(iso):
    """'2026-11-25' -> 'Wed 25 Nov'. Falls back to the original text if it is not an ISO date."""
    try:
        day = datetime.strptime(str(iso), "%Y-%m-%d")
    except ValueError:
        return str(iso)
    return f"{day:%a} {day.day} {day:%b}"


def describe(booking):
    return f"{booking['resource']} on {_friendly_date(booking['date'])} ({SLOT_LABELS.get(booking['time_slot'], booking['time_slot'])})"


def _notify(cursor, username, message):
    cursor.execute("INSERT INTO notifications (username, message) VALUES (%s, %s)", (username, message[:255]))


def record_event(cursor, booking_id, from_status, to_status, actor, note=None):
    cursor.execute(
        "INSERT INTO booking_events (booking_id, from_status, to_status, actor, note) VALUES (%s, %s, %s, %s, %s)",
        (booking_id, from_status, to_status, actor, note or None),
    )


def _set_status(cursor, booking, target, actor, note):
    cursor.execute("UPDATE bookings SET status = %s, decision_note = %s WHERE id = %s",
                   (target, (note or None), booking["id"]))
    record_event(cursor, booking["id"], booking["status"], target, actor, note)


def apply_transition(cursor, booking, target, actor, note):
    """Carry out an allowed change (call check_transition first). `actor` is a username or "system".

    Runs inside the caller's transaction. Returns the list of other bookings that were changed automatically.
    """
    note = (note or "").strip() or None
    _set_status(cursor, booking, target, actor, note)

    text = describe(booking)
    owner_is_actor = actor == booking["username"]
    if target == REVIEW:
        _notify(cursor, booking["username"], f"Your booking for {text} is now under review.")
    elif target == APPROVED:
        _notify(cursor, booking["username"], f"Your booking for {text} has been approved.")
    elif target == REJECTED:
        _notify(cursor, booking["username"], f"Your booking for {text} was rejected: {note}")
    elif target == CANCELLED and not owner_is_actor:
        _notify(cursor, booking["username"], f"Your booking for {text} was cancelled by the administration: {note}")

    changed = []
    if target == APPROVED:
        changed = _reject_competitors(cursor, booking)
    return changed


def _reject_competitors(cursor, approved):
    """The slot now belongs to `approved`: reject every other open request for it."""
    cursor.execute(
        "SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') AS date, time_slot, status "
        "FROM bookings WHERE resource = %s AND booking_date = %s AND time_slot = %s "
        "AND status IN ('Pending', 'Under Review') AND id <> %s FOR UPDATE",
        (approved["resource"], approved["date"], approved["time_slot"], approved["id"]),
    )
    others = [dict(zip(("id", "username", "resource", "date", "time_slot", "status"), row)) for row in cursor.fetchall()]
    for other in others:
        reason = "The slot was approved for another request."
        _set_status(cursor, other, REJECTED, "system", reason)
        _notify(cursor, other["username"], f"Your booking for {describe(other)} was rejected: {reason}")
    return others


def release_slot(cursor, resource, day, time_slot):
    """A maintenance block now covers this slot: reject open requests and cancel any approved booking."""
    cursor.execute(
        "SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') AS date, time_slot, status "
        "FROM bookings WHERE resource = %s AND booking_date = %s AND time_slot = %s "
        "AND status IN ('Pending', 'Under Review', 'Approved') FOR UPDATE",
        (resource, day, time_slot),
    )
    affected = [dict(zip(("id", "username", "resource", "date", "time_slot", "status"), row)) for row in cursor.fetchall()]
    reason = "The resource is blocked for maintenance."
    for booking in affected:
        target = CANCELLED if booking["status"] == APPROVED else REJECTED
        _set_status(cursor, booking, target, "system", reason)
        verb = "cancelled" if target == CANCELLED else "rejected"
        _notify(cursor, booking["username"], f"Your booking for {describe(booking)} was {verb}: {reason}")
    return affected
