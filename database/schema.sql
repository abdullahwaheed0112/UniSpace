-- UniSpace+ database schema (MySQL 8.0.16 or later: CHECK constraints and generated columns are used).
--
--   mysql -u root -p < database/schema.sql
--   python backend/seed_admin.py          # creates the first admin account
--
-- Databases created from an older version of this file: apply the files in database/migrations/ in order.

-- Create the database
CREATE DATABASE IF NOT EXISTS unispace;

-- Select the database
USE unispace;

-- Users. Emails and usernames are unique; passwords are salted scrypt hashes, never plain text.
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    CONSTRAINT uq_users_username UNIQUE (username),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT chk_users_role CHECK (role IN ('student', 'admin'))
);

-- The first admin account is created by backend/seed_admin.py (no default password is stored in this file).

-- Bookings move through a workflow (see backend/workflow.py):
--   Pending -> Under Review -> Approved -> Cancelled, with Rejected and Cancelled as exits.
-- Two generated columns turn business rules into database constraints:
--   active_request: a user cannot hold two open (Pending / Under Review / Approved) requests for the same slot
--   approved_slot:  a slot can have at most one Approved booking
-- (MySQL allows many NULLs in a unique index, so Rejected and Cancelled rows never collide.)
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    resource VARCHAR(50) NOT NULL,
    booking_date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    decision_note VARCHAR(255) NULL,  -- the reason given when a booking is rejected or cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active_request VARCHAR(160) GENERATED ALWAYS AS (
        IF(status IN ('Pending', 'Under Review', 'Approved'), CONCAT_WS('|', username, resource, booking_date, time_slot), NULL)
    ) STORED,
    approved_slot VARCHAR(120) GENERATED ALWAYS AS (
        IF(status = 'Approved', CONCAT_WS('|', resource, booking_date, time_slot), NULL)
    ) STORED,
    CONSTRAINT chk_bookings_status CHECK (status IN ('Pending', 'Under Review', 'Approved', 'Rejected', 'Cancelled')),
    CONSTRAINT uq_bookings_active_request UNIQUE (active_request),
    CONSTRAINT uq_bookings_approved_slot UNIQUE (approved_slot),
    -- RESTRICT (the default): MySQL does not allow CASCADE on a column used by a stored generated column,
    -- and the app has no "delete account" feature, so users with bookings simply cannot be removed.
    CONSTRAINT fk_bookings_user FOREIGN KEY (username) REFERENCES users (username)
);

-- Audit trail: one row per status change, so a booking's history can be shown and nothing happens silently.
-- actor is the username of whoever made the change, or 'system' for automatic changes.
CREATE TABLE IF NOT EXISTS booking_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    booking_id INT NOT NULL,
    from_status VARCHAR(20) NULL,
    to_status VARCHAR(20) NOT NULL,
    actor VARCHAR(50) NOT NULL,
    note VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_events_booking FOREIGN KEY (booking_id) REFERENCES bookings (id) ON DELETE CASCADE,
    INDEX idx_events_booking (booking_id, created_at)
);

-- Maintenance blocks set by admins. The same slot cannot be blocked twice.
CREATE TABLE IF NOT EXISTS blocked_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    resource VARCHAR(50) NOT NULL,
    blocked_date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_blocked_slot UNIQUE (resource, blocked_date, time_slot)
);

-- In-app notifications for a user.
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    message VARCHAR(255) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE
);
