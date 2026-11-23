-- Migration: multi-step booking workflow (Pending -> Under Review -> Approved -> Cancelled, with audit trail).
-- Run against the `unispace` database after 002_constraints.sql:
--   mysql -u root -p unispace < database/migrations/003_booking_workflow.sql

-- 1) New statuses and a place for the reason behind a rejection or cancellation.
ALTER TABLE bookings DROP CHECK chk_bookings_status;
ALTER TABLE bookings DROP INDEX uq_bookings_active_request;
ALTER TABLE bookings DROP COLUMN active_request;

ALTER TABLE bookings
    ADD COLUMN decision_note VARCHAR(255) NULL AFTER status,
    ADD COLUMN active_request VARCHAR(160) GENERATED ALWAYS AS (
        IF(status IN ('Pending', 'Under Review', 'Approved'), CONCAT_WS('|', username, resource, booking_date, time_slot), NULL)
    ) STORED,
    ADD CONSTRAINT chk_bookings_status CHECK (status IN ('Pending', 'Under Review', 'Approved', 'Rejected', 'Cancelled')),
    ADD CONSTRAINT uq_bookings_active_request UNIQUE (active_request);

-- 2) The audit trail.
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

-- 3) Give existing bookings a history: their creation, and (if decided) their outcome.
INSERT INTO booking_events (booking_id, from_status, to_status, actor, created_at)
    SELECT id, NULL, 'Pending', username, created_at FROM bookings;
INSERT INTO booking_events (booking_id, from_status, to_status, actor, created_at)
    SELECT id, 'Pending', status, 'system', created_at FROM bookings WHERE status <> 'Pending';
