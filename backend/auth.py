"""Password hashing and signed login tokens (permission checks are added in a later commit)."""
import hmac

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

import config

# Werkzeug hashes look like "scrypt:32768:8:1$<salt>$<hash>" (or "pbkdf2:sha256:...$...$...").
_HASH_PREFIXES = ("scrypt:", "pbkdf2:")

# A valid hash of a random string, used so that "unknown email" costs about the same time as "wrong password".
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def hash_password(password):
    """Return a salted scrypt hash for storage. The plain password is never stored."""
    return generate_password_hash(password)


def is_hashed(stored):
    return isinstance(stored, str) and stored.startswith(_HASH_PREFIXES)


def verify_password(stored, supplied):
    """Check a supplied password against the stored value.

    Returns (ok, needs_rehash). `needs_rehash` is True when the stored value was a legacy plain-text password
    from before hashing was introduced: the caller should then store hash_password(supplied).
    """
    if stored is None:
        check_password_hash(_DUMMY_HASH, supplied)  # keep timing similar for unknown accounts
        return False, False
    if is_hashed(stored):
        return check_password_hash(stored, supplied), False
    # Legacy plain-text row: compare in constant time, then ask the caller to upgrade it.
    ok = hmac.compare_digest(stored.encode("utf-8"), supplied.encode("utf-8"))
    return ok, ok


# --- Login tokens ---
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="unispace-login")


def issue_token(user_id):
    """Return a signed, time-limited token that identifies a user. It carries only the user id."""
    return _serializer.dumps({"uid": user_id})


def read_token(token):
    """Return the user id inside a valid token, or None if it is missing, forged or expired."""
    if not token:
        return None
    try:
        payload = _serializer.loads(token, max_age=config.TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    return payload.get("uid") if isinstance(payload, dict) else None
