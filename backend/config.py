"""Application settings, read from environment variables.

Copy `.env.example` to `.env` and edit it; the file is loaded automatically if python-dotenv is installed.
Nothing in this file is a secret: real values belong in the environment, never in git.
"""
import logging
import os
import secrets
from pathlib import Path

try:  # optional convenience: load backend/../.env if python-dotenv is available
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def _flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


# --- MySQL ---
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "3306"))
DB_USER = os.environ.get("DB_USER", "root")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DB_NAME = os.environ.get("DB_NAME", "unispace")

# --- Flask ---
# Debug mode exposes an interactive debugger, so it is OFF unless you switch it on explicitly.
DEBUG = _flag("FLASK_DEBUG", "0")
HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
PORT = int(os.environ.get("FLASK_PORT", "5000"))

# Origins allowed to call the API from a browser (the frontend dev server).
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",")
    if o.strip()
]

# --- Login tokens ---
# Tokens are signed with SECRET_KEY. Set it in the environment (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`).
# If it is missing, a random key is generated for this run only: the app works, but every restart signs everyone out.
SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    logging.getLogger(__name__).warning("SECRET_KEY is not set: using a temporary key, logins will not survive a restart.")

TOKEN_MAX_AGE_SECONDS = int(os.environ.get("TOKEN_MAX_AGE_SECONDS", str(8 * 60 * 60)))  # 8 hours
