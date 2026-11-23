from flask import Flask, request, jsonify, g
from flask_cors import CORS
import mysql.connector

import config
from auth import admin_required, hash_password, issue_token, login_required, student_required, verify_password
from db import get_db

# Create the Flask app
app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)  # only the configured frontend origins may call the API


# Route: POST /signup
@app.route("/signup", methods=["POST"])
def signup():
    # Get the JSON data sent from the frontend
    data = request.get_json()

    username = data["username"]
    email = data["email"]
    password = data["password"]

    # Connect to MySQL
    db = get_db()

    cursor = db.cursor()

    # Insert the user into the database
    sql = "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)"
    values = (username, email, hash_password(password))  # only the salted hash is stored

    try:
        cursor.execute(sql, values)
        db.commit()
        return jsonify({"message": "Sign up successful!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        db.close()


# Route: POST /signin
@app.route("/signin", methods=["POST"])
def signin():
    data = request.get_json()

    email = data["email"]
    password = data["password"]

    # Connect to MySQL
    db = get_db()

    cursor = db.cursor()

    # Look the user up by email, then verify the password against the stored hash
    cursor.execute("SELECT id, username, email, role, password FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    ok, needs_rehash = verify_password(user[4] if user else None, password)
    if ok and needs_rehash:
        # Legacy plain-text password from before hashing: upgrade it now that we know the real password
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hash_password(password), user[0]))
        db.commit()

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
    else:
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
    data = request.get_json()
    username = g.user["username"]  # from the verified token, never from the request body
    resource = data.get("resource")
    booking_date = data.get("date")
    time_slot = data.get("timeSlot")

    db = get_db()
    cursor = db.cursor()

    # Check if slot is blocked
    cursor.execute("SELECT id FROM blocked_slots WHERE resource = %s AND blocked_date = %s AND time_slot = %s", (resource, booking_date, time_slot))
    if cursor.fetchone():
        cursor.close()
        db.close()
        return jsonify({"message": "This slot has been blocked by the administration."}), 400

    # Insert booking
    sql = "INSERT INTO bookings (username, resource, booking_date, time_slot, status) VALUES (%s, %s, %s, %s, 'Pending')"
    try:
        cursor.execute(sql, (username, resource, booking_date, time_slot))
        db.commit()
        return jsonify({"message": "Booking successful!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
    finally:
        cursor.close()
        db.close()

@app.route("/bookings", methods=["GET"])
@login_required
def get_bookings():
    # Admins see every booking; a student only ever sees their own (any ?username= in the URL is ignored)
    username = g.user["username"] if g.user["role"] != "admin" else None

    db = get_db()
    cursor = db.cursor(dictionary=True)

    if username:
        sql = "SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') as date, time_slot as timeSlot, status FROM bookings WHERE username = %s ORDER BY booking_date ASC"
        cursor.execute(sql, (username,))
    else:
        sql = "SELECT id, username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') as date, time_slot as timeSlot, status FROM bookings ORDER BY booking_date ASC"
        cursor.execute(sql)

    bookings = cursor.fetchall()
    
    cursor.close()
    db.close()
    return jsonify(bookings), 200

@app.route("/bookings/<int:booking_id>/status", methods=["PUT"])
@admin_required
def update_booking_status(booking_id):
    data = request.get_json()
    new_status = data.get("status")

    db = get_db()
    cursor = db.cursor()

    sql = "UPDATE bookings SET status = %s WHERE id = %s"
    try:
        cursor.execute(sql, (new_status, booking_id))
        
        # Add notification logic
        cursor.execute("SELECT username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') FROM bookings WHERE id = %s", (booking_id,))
        booking = cursor.fetchone()
        if booking:
            msg = f"Your booking for {booking[1]} on {booking[2]} has been {new_status}."
            cursor.execute("INSERT INTO notifications (username, message) VALUES (%s, %s)", (booking[0], msg))
            
        db.commit()
        return jsonify({"message": f"Booking {booking_id} updated to {new_status}"}), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
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

    sql = ("SELECT resource, DATE_FORMAT(booking_date, '%Y-%m-%d') AS date, time_slot AS timeSlot, "
           "IF(MAX(status = 'Approved') = 1, 'Approved', 'Pending') AS status "
           "FROM bookings WHERE status IN ('Pending', 'Approved')")
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
    except mysql.connector.Error:
        return jsonify({"message": "Invalid filter."}), 400
    finally:
        cursor.close()
        db.close()


# --- BLOCKED SLOTS API ---

@app.route("/blocked_slots", methods=["POST"])
@admin_required
def block_slot():
    data = request.get_json()
    resource = data.get("resource")
    blocked_date = data.get("date")
    time_slot = data.get("time")

    db = get_db()
    cursor = db.cursor()

    sql = "INSERT INTO blocked_slots (resource, blocked_date, time_slot) VALUES (%s, %s, %s)"
    try:
        cursor.execute(sql, (resource, blocked_date, time_slot))
        db.commit()
        
        # Auto-reject any existing pending bookings for this newly blocked slot
        cursor.execute("SELECT username, resource, DATE_FORMAT(booking_date, '%Y-%m-%d') FROM bookings WHERE resource = %s AND booking_date = %s AND time_slot = %s AND status = 'Pending'", (resource, blocked_date, time_slot))
        affected = cursor.fetchall()
        
        reject_sql = "UPDATE bookings SET status = 'Rejected' WHERE resource = %s AND booking_date = %s AND time_slot = %s AND status = 'Pending'"
        cursor.execute(reject_sql, (resource, blocked_date, time_slot))
        
        for user_row in affected:
            msg = f"Your pending booking for {user_row[1]} on {user_row[2]} was automatically rejected due to a maintenance block."
            cursor.execute("INSERT INTO notifications (username, message) VALUES (%s, %s)", (user_row[0], msg))
            
        db.commit()

        return jsonify({"message": "Slot blocked successfully!"}), 201
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
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

    sql = "DELETE FROM blocked_slots WHERE id = %s"
    try:
        cursor.execute(sql, (slot_id,))
        db.commit()
        return jsonify({"message": "Slot unblocked successfully!"}), 200
    except mysql.connector.Error as err:
        return jsonify({"message": f"Error: {err}"}), 500
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
    
    sql = "SELECT id, message, is_read, DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as date FROM notifications WHERE username = %s ORDER BY created_at DESC"
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