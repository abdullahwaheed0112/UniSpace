-- Migration for databases created before passwords were hashed.
-- 1) Widen the column so it can hold a hash.
ALTER TABLE users MODIFY password VARCHAR(255) NOT NULL;
-- 2) Existing plain-text passwords are upgraded to hashes automatically the next time each user signs in.
--    To stop accepting any remaining plain-text rows immediately, reset those users' passwords.
