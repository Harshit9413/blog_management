from fastapi import Depends, Request,HTTPException
from sqlalchemy.orm import Session

import models
from database import sessionlocal


def get_db():
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()


class AuthenticationError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        self.message     = message
        self.status_code = status_code


class AdminPermissionError(Exception):
    def __init__(self, message: str = "Only admins can perform this action."):
        self.message     = message
        self.status_code = 403


def get_current_user(request: Request, db: Session = Depends(get_db)):
    email = request.cookies.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not logged in")
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_admin_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if current_user.role not in {"superadmin", "clientadmin"}:
        raise AdminPermissionError()

    return current_user