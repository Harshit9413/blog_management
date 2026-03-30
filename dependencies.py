from fastapi import Depends, Request
from sqlalchemy.orm import Session

import models
from database import sessionlocal


# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE DEPENDENCY
# ─────────────────────────────────────────────────────────────────────────────

def get_db():
    """Yield a database session and close it when the request finishes."""
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
#  CUSTOM EXCEPTIONS
# ─────────────────────────────────────────────────────────────────────────────

class AuthenticationError(Exception):
    """
    Raised when a request is not authenticated or the account is blocked.
    Caught by the global exception handler in main.py.
    """
    def __init__(self, message: str, status_code: int = 401):
        self.message     = message
        self.status_code = status_code


class AdminPermissionError(Exception):
    """
    Raised when a logged-in user tries to perform an admin-only action.
    Caught by the global exception handler in main.py.
    """
    def __init__(self, message: str = "Only admins can perform this action."):
        self.message     = message
        self.status_code = 403


# ─────────────────────────────────────────────────────────────────────────────
#  CURRENT USER DEPENDENCY
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    request: Request,
    db:      Session = Depends(get_db),
) -> models.User:
    """
    Read the `user_email` cookie set by POST /login and return the User object.

    Raises:
        AuthenticationError 401 — cookie missing or user not found.
        AuthenticationError 403 — account blocked by admin.
    """
    email = request.cookies.get("user_email")

    if not email:
        raise AuthenticationError(
            "Not authenticated. Please log in first.",
            status_code=401,
        )

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        raise AuthenticationError(
            "User not found. Please log in again.",
            status_code=401,
        )

    if not user.is_active:
        raise AuthenticationError(
            "Your account has been blocked by an administrator.",
            status_code=403,
        )

    return user


# ─────────────────────────────────────────────────────────────────────────────
#  ADMIN ONLY DEPENDENCY
# ─────────────────────────────────────────────────────────────────────────────

def get_admin_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """
    Extends get_current_user — also checks the user is superadmin or clientadmin.

    Raises:
        AdminPermissionError 403 — user is authenticated but not an admin.
    """
    if current_user.role not in {"superadmin", "clientadmin"}:
        raise AdminPermissionError()

    return current_user