"""Application settings, read from environment variables.

Copy `.env.example` to `.env` and edit it; the file is loaded automatically if python-dotenv is installed.
Nothing in this file is a secret: real values belong in the environment, never in git.
"""
import os
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
