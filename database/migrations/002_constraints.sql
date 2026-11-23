-- Migration for databases created before the integrity constraints were added.
-- Run it against the `unispace` database: mysql -u root -p unispace < database/migrations/002_constraints.sql
--
-- It FAILS (safely, nothing is half-applied per statement) if existing data breaks a rule. Check first with:
--   SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;            -- duplicate emails
--   SELECT username, COUNT(*) FROM users GROUP BY username HAVING COUNT(*) > 1;      -- duplicate usernames
--   SELECT username FROM bookings WHERE username NOT IN (SELECT username FROM users); -- orphaned bookings
-- and remove or fix the offending rows (the old schema.sql could create a duplicate admin on every run).

ALTER TABLE users
    ADD CONSTRAINT uq_users_username UNIQUE (username),
    ADD CONSTRAINT uq_users_email UNIQUE (email),
    ADD CONSTRAINT chk_users_role CHECK (role IN ('student', 'admin'));

ALTER TABLE bookings
    ADD COLUMN active_request VARCHAR(160) GENERATED ALWAYS AS (
        IF(status IN ('Pending', 'Approved'), CONCAT_WS('|', username, resource, booking_date, time_slot), NULL)
    ) STORED,
    ADD COLUMN approved_slot VARCHAR(120) GENERATED ALWAYS AS (
        IF(status = 'Approved', CONCAT_WS('|', resource, booking_date, time_slot), NULL)
    ) STORED,
    ADD CONSTRAINT chk_bookings_status CHECK (status IN ('Pending', 'Approved', 'Rejected')),
    ADD CONSTRAINT uq_bookings_active_request UNIQUE (active_request),
    ADD CONSTRAINT uq_bookings_approved_slot UNIQUE (approved_slot),
    ADD CONSTRAINT fk_bookings_user FOREIGN KEY (username) REFERENCES users (username);

ALTER TABLE blocked_slots
    ADD CONSTRAINT uq_blocked_slot UNIQUE (resource, blocked_date, time_slot);

ALTER TABLE notifications
    ADD CONSTRAINT fk_notifications_user FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE;
