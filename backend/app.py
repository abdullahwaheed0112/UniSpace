from flask import Flask, request, jsonify, g
from flask_cors import CORS
import mysql.connector

import config
from auth import admin_required, hash_password, issue_token, login_required, student_required, verify_password
from db import get_db
from validators import RESOURCES, parse_date, validate_block, validate_booking, validate_signup
from workflow import PENDING, STATUSES, apply_transition, check_transition, record_event, release_slot, roles_for

# Create the Flask app
app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)  # only the configured frontend origins may call the API


# Route: POST /signup
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")

    error = validate_signup(username, email, password)
    if error:
        return jsonify({"message": error}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hash_password(password)))  # only the salted hash is stored
        db.commit()
        return jsonify({"message": "Sign up successful!"}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"message": "That username or email is already registered."}), 409
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("sign up failed")
        return jsonify({"message": "Something went wrong on the server. Please try again."}), 500
    finally:
        cursor.close()
        db.close()

# Route: POST /signin
@app.route("/signin", methods=["POST"])
def signin():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    if not email or not isinstance(password, str) or not password:
        return jsonify({"message": "Email and password are required."}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        # Look the user up by email, then verify the password against the stored hash
        cursor.execute("SELECT id, username, email, role, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        ok, needs_rehash = verify_password(user[4] if user else None, password)
        if ok and needs_rehash:
            # Legacy plain-text password from before hashing: upgrade it now that we know the real password
            cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hash_password(password), user[0]))
            db.commit()
    finally:
        cursor.close()
        db.close()

    if user and ok:
        # user[0]=id, user[1]=username, user[2]=email, user[3]=role
        return jsonify({
            "message": f"Welcome back, {user[1]}!",
            "username": user[1],
            "role": user[3],
            "token": issue_token(user[0])
        }), 200
    return jsonify({"message": "Invalid email or password!"}), 401

# Route: GET /me  (who does this token belong to?)
@app.route("/me", methods=["GET"])
@login_required
def me():
    return jsonify({"username": g.user["username"], "role": g.user["role"]}), 200


# --- BOOKINGS API ---

@app.route("/bookings", methods=["POST"])
@student_required
def create_booking():
    data = request.get_json(silent=True) or {}
    username = g.user["username"]  # from the verified token, never from the request body
    resource = data.get("resource")
    booking_date = data.get("date")
    time_slot = data.get("timeSlot")

    error = validate_booking(resource, booking_date, time_slot)
    if error:
        return jsonify({"message": error}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        # Check if slot is blocked
        cursor.execute("SELECT id FROM blocked_slots WHERE resource = %s AND blocked_date = %s AND time_slot = %s",
                       (resource, booking_date, time_slot))
        if cursor.fetchone():
            return jsonify({"message": "This slot has been blocked by the administration."}), 400

        cursor.execute("INSERT INTO bookings (username, resource, booking_date, time_slot, status) "
                       "VALUES (%s, %s, %s, %s, %s)", (username, resource, booking_date, time_slot, PENDING))
        record_event(cursor, cursor.lastrowid, None, PENDING, username)
        db.commit()
        return jsonify({"message": "Booking successful!"}), 201
    except mysql.connector.IntegrityError:
        db.rollback()
        return jsonify({"message": "You already have a request or booking for this slot."}), 409
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("create booking failed")
        return jsonify({"message": "Something went wrong on the server. Please try again."}), 500
    finally:
        cursor.close()
        db.close()

@app.route("/bookings", methods=["GET"])
@login_required
def get_bookings():
    # Admins see every booking; a student only ever sees their own (any ?username= in the URL is ignored)
    sql = ("SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') AS date, time_slot AS timeSlot, "
           "status, decision_note AS note, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') AS createdAt FROM bookings")
    params = ()
    if g.user["role"] != "admin":
        sql += " WHERE username = %s"
        params = (g.user["username"],)
    sql += " ORDER BY booking_date ASC, time_slot ASC"

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return jsonify(cursor.fetchall()), 200
    finally:
        cursor.close()
        db.close()


@app.route("/bookings/<int:booking_id>", methods=["GET"])
@login_required
def get_booking(booking_id):
    """One booking with its history (the audit trail). Only the owner and admins can see it."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') AS date, "
                       "time_slot AS timeSlot, status, decision_note AS note FROM bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        if not booking or (g.user["role"] != "admin" and booking["username"] != g.user["username"]):
            return jsonify({"message": "Booking not found."}), 404  # same answer for "not yours" and "does not exist"

        cursor.execute("SELECT from_status AS fromStatus, to_status AS toStatus, actor, note, "
                       "DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') AS at FROM booking_events "
                       "WHERE booking_id = %s ORDER BY created_at ASC, id ASC", (booking_id,))
        booking["history"] = cursor.fetchall()
        return jsonify(booking), 200
    finally:
        cursor.close()
        db.close()

@app.route("/bookings/<int:booking_id>/status", methods=["PUT"])
@login_required
def update_booking_status(booking_id):
    """Move a booking through the workflow (see backend/workflow.py). Body: {"status": "...", "note": "..."}."""
    data = request.get_json(silent=True) or {}
    target = data.get("status")
    note = data.get("note")
    if target not in STATUSES:
        return jsonify({"message": "Unknown status."}), 400
    if note is not None and not isinstance(note, str):
        return jsonify({"message": "The reason must be text."}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        # Lock the row so two admins cannot decide the same booking at the same moment
        cursor.execute("SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d'), time_slot, status "
                       "FROM bookings WHERE id = %s FOR UPDATE", (booking_id,))
        row = cursor.fetchone()
        booking = dict(zip(("id", "username", "resource", "date", "time_slot", "status"), row)) if row else None
        roles = roles_for(g.user, booking) if booking else set()
        if not roles:  # no such booking, or somebody else's: the same answer for both
            return jsonify({"message": "Booking not found."}), 404

        problem = check_transition(booking["status"], target, roles, note)
        if problem:
            return jsonify({"message": problem[1]}), problem[0]

        changed = apply_transition(cursor, booking, target, g.user["username"], note)
        db.commit()
        return jsonify({"message": f"Booking {booking_id} is now {target}.", "status": target,
                        "alsoRejected": len(changed)}), 200
    except mysql.connector.IntegrityError:
        db.rollback()
        return jsonify({"message": "Another booking is already approved for that slot."}), 409
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("update booking status failed")
        return jsonify({"message": "Something went wrong on the server. Please try again."}), 500
    finally:
        cursor.close()
        db.close()

# --- AVAILABILITY (public) ---

@app.route("/availability", methods=["GET"])
def availability():
    """Which slots have a request or an approved booking, without revealing who made it.

    Public on purpose: visitors can see the grid, but no usernames leave the server.
    Query: ?resource=Lab&from=2026-11-23&to=2026-11-29 (all three optional).
    """
    resource = request.args.get("resource")
    date_from = request.args.get("from")
    date_to = request.args.get("to")
    if resource and resource not in RESOURCES:
        return jsonify({"message": "Unknown resource."}), 400
    if (date_from and parse_date(date_from) is None) or (date_to and parse_date(date_to) is None):
        return jsonify({"message": "Dates must look like 2026-11-26."}), 400

    sql = ("SELECT resource, DATE_FORMAT(booking_date, '%Y-%m-%d') AS date, time_slot AS timeSlot, "
           "IF(MAX(status = 'Approved') = 1, 'Approved', 'Pending') AS status "
           "FROM bookings WHERE status IN ('Pending', 'Under Review', 'Approved')")
    params = []
    if resource:
        sql += " AND resource = %s"
        params.append(resource)
    if date_from:
        sql += " AND booking_date >= %s"
        params.append(date_from)
    if date_to:
        sql += " AND booking_date <= %s"
        params.append(date_to)
    sql += " GROUP BY resource, booking_date, time_slot ORDER BY booking_date ASC"

    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return jsonify(cursor.fetchall()), 200
    finally:
        cursor.close()
        db.close()

# --- BLOCKED SLOTS API ---

@app.route("/blocked_slots", methods=["POST"])
@admin_required
def block_slot():
    data = request.get_json(silent=True) or {}
    resource = data.get("resource")
    blocked_date = data.get("date")
    time_slot = data.get("time")

    error = validate_block(resource, blocked_date, time_slot)
    if error:
        return jsonify({"message": error}), 400

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO blocked_slots (resource, blocked_date, time_slot) VALUES (%s, %s, %s)",
                       (resource, blocked_date, time_slot))
        # Open requests are rejected and an approved booking is cancelled; each student is notified
        affected = release_slot(cursor, resource, blocked_date, time_slot)
        db.commit()
        return jsonify({"message": "Slot blocked successfully!", "affectedBookings": len(affected)}), 201
    except mysql.connector.IntegrityError:
        db.rollback()
        return jsonify({"message": "That slot is already blocked."}), 409
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("block slot failed")
        return jsonify({"message": "Something went wrong on the server. Please try again."}), 500
    finally:
        cursor.close()
        db.close()

@app.route("/blocked_slots", methods=["GET"])
def get_blocked_slots():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    sql = "SELECT id, resource, DATE_FORMAT(blocked_date, '%Y-%m-%d') as date, time_slot as time FROM blocked_slots ORDER BY blocked_date ASC"
    cursor.execute(sql)
    blocked_slots = cursor.fetchall()
    
    cursor.close()
    db.close()
    return jsonify(blocked_slots), 200

@app.route("/blocked_slots/<int:slot_id>", methods=["DELETE"])
@admin_required
def unblock_slot(slot_id):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM blocked_slots WHERE id = %s", (slot_id,))
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({"message": "That slot is not blocked."}), 404
        return jsonify({"message": "Slot unblocked successfully!"}), 200
    except mysql.connector.Error:
        db.rollback()
        app.logger.exception("unblock slot failed")
        return jsonify({"message": "Something went wrong on the server. Please try again."}), 500
    finally:
        cursor.close()
        db.close()

# --- NOTIFICATIONS API ---

@app.route("/notifications", methods=["GET"])
@login_required
def get_notifications():
    username = g.user["username"]  # always the caller's own notifications

    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    sql = "SELECT id, message, is_read, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as date FROM notifications WHERE username = %s ORDER BY created_at DESC, id DESC"
    cursor.execute(sql, (username,))
    notifications = cursor.fetchall()
    
    cursor.close()
    db.close()
    return jsonify(notifications), 200

@app.route("/notifications/read", methods=["PUT"])
@login_required
def mark_notifications_read():
    username = g.user["username"]

    db = get_db()
    cursor = db.cursor()
    
    sql = "UPDATE notifications SET is_read = TRUE WHERE username = %s AND is_read = FALSE"
    try:
        cursor.execute(sql, (username,))
        db.commit()
        return jsonify({"message": "Notifications marked as read"}), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        db.close()

# Run the server
if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)