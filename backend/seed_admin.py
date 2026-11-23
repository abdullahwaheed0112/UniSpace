"""Create the first admin account (safe to run more than once).

    ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=choose-a-long-passphrase python seed_admin.py

If the variables are not set, the script asks for them. The password is hashed before it is stored.
"""
import getpass
import os
import sys

from auth import hash_password
from db import get_db

MIN_PASSWORD_LENGTH = 8


def main():
    email = os.environ.get("ADMIN_EMAIL") or input("Admin email: ").strip()
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    username = os.environ.get("ADMIN_USERNAME", "Admin")

    if "@" not in email:
        sys.exit("That does not look like an email address.")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"Use at least {MIN_PASSWORD_LENGTH} characters for the admin password.")

    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            print(f"{email} already exists, nothing changed.")
            return
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, 'admin')",
            (username, email, hash_password(password)),
        )
        db.commit()
        print(f"Admin account created for {email}.")
    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    main()
