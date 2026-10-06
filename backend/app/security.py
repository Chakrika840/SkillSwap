"""
Authentication: bcrypt password hashing, JWT tokens, and the 'who is calling?' dependencies.

Flow:  login -> create_token(email, role) -> React stores it -> every request sends
       "Authorization: Bearer <token>" -> get_current_user() checks it before the endpoint runs.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .config import settings
from .database import get_db
from .errors import ApiError
from .models import Role, User

ALGORITHM = "HS256"
_bearer = HTTPBearer(auto_error=False)   # we raise our own 401 with our own message


# ------------------------------------------------------------------ passwords
def _to_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]   # bcrypt only uses the first 72 bytes


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(password), hashed.encode("utf-8"))
    except ValueError:
        return False


# ------------------------------------------------------------------ tokens
def create_token(email: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,                     # subject = who the token belongs to
        "role": role,
        "iat": now,                       # issued at
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),   # expiry
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    """Returns the email inside a valid token, or None if it is invalid, tampered with or expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


# ------------------------------------------------------------------ dependencies
def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: DbSession = Depends(get_db),
) -> User:
    """Runs before every protected endpoint (like Spring's JwtAuthFilter)."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError.unauthorized()
    email = decode_token(credentials.credentials)
    if not email:
        raise ApiError.unauthorized()
    user = db.scalar(select(User).where(User.email == email))
    # Suspended users are rejected even if their token has not expired yet.
    if user is None or not user.active:
        raise ApiError.unauthorized()
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.ADMIN:
        raise ApiError.forbidden("You don't have access to this page.")
    return user
