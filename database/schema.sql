-- Create the database
CREATE DATABASE IF NOT EXISTS unispace;

-- Select the database
USE unispace;

-- Create the users table
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    password VARCHAR(255) NOT NULL,  -- salted scrypt hash, never the plain password
    role VARCHAR(20) DEFAULT 'student'
);

-- The first admin account is created by backend/seed_admin.py (no default password is stored in this file).

-- Create bookings table
CREATE TABLE IF NOT EXISTS bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    resource VARCHAR(50) NOT NULL,
    booking_date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    status VARCHAR(20) DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Note: Removed user_id foreign key constraint temporarily for simpler migration from local storage
-- since we only store the username in local storage currently. 

-- Create blocked slots table
CREATE TABLE IF NOT EXISTS blocked_slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    resource VARCHAR(50) NOT NULL,
    blocked_date DATE NOT NULL,
    time_slot VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    message VARCHAR(255) NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
