import os
import re
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

import auth
import models
from database import sessionlocal, engine

models.Base.metadata.create_all(bind=engine)
load_dotenv()

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
templates.env.cache = None   # 🔥 disable cache completely
app       = FastAPI()

SENDER_EMAIL    = os.getenv("SENDER_EMAIL",    "harshitjangid99291@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "cqijkpmkflgowpky")


def send_email(to_email: str, otp: str) -> tuple[bool, str]:
    try:
        msg = MIMEText(f"Your OTP is: {otp}", "plain")
        msg["Subject"] = "OTP Code"
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

        print("✅ Email sent")
        return True, ""   # ✅ FIXED

    except Exception as e:
        print("❌ Email error:", e)
        return False, str(e)   # ✅ FIXED



class UserCreate(BaseModel):
    email:    EmailStr
    password: str
    phone:    str | None = None
    gender:   str | None = None

    @field_validator("phone")
    def validate_phone(cls, v):
        if not v:
            return v
        if not re.match(r"^[6-9]\d{9}$", v):
            raise ValueError("Invalid phone (10 digits, start with 6-9)")
        return v
    

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a number")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain a letter")
        return v


class UserLogin(BaseModel):
    email:    EmailStr
    password: str


class ForgotPassword(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp:   str


class ResetPassword(BaseModel):
    email:        EmailStr
    new_password: str

    @field_validator("new_password")
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a number")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain a letter")
        return v


class EmailUpdate(BaseModel):
    email: str


class UpdateRoleBody(BaseModel):
    role: str

    @field_validator("role")
    def validate_role(cls, v):
        if v not in {"user", "clientadmin"}:
            raise ValueError("Role must be 'user' or 'clientadmin'")
        return v


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_db():
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()


def get_role_dashboard(role: str) -> str:
    return {
        "superadmin":  "/super-admin/dashboard",
        "clientadmin": "/client-admin/dashboard",
    }.get(role, "/dashboard")


def require_role(request: Request, db: Session, role: str):
    email = request.cookies.get("user_email")
    if not email:
        return None, RedirectResponse("/login?msg=Please login first", status_code=303)
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not user.is_active:
        return None, RedirectResponse("/login?msg=Account blocked or invalid", status_code=303)
    if user.role != role:
        return None, RedirectResponse(get_role_dashboard(user.role), status_code=303)
    return user, None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [e["msg"].replace("Value error, ", "") for e in exc.errors()]
    return JSONResponse(status_code=400, content={"error": "\n".join(errors)})


# ─────────────────────────────────────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if request.cookies.get("user_email"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/register")
def register(user_data: UserCreate, request: Request, db: Session = Depends(get_db)):
    
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    
    if existing_user:
        return JSONResponse({"error": "Email already registered"}, status_code=400)

    new_user = models.User(
        email    = user_data.email,
        password = auth.hash_password(user_data.password),
        phone    = user_data.phone,
        gender   = user_data.gender,
        role     = "user",
    )

    db.add(new_user)
    db.commit()

    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    email = request.cookies.get("user_email")
    role  = request.cookies.get("user_role")

    if email:
        return RedirectResponse(get_role_dashboard(role or "user"), status_code=303)

    msg = request.query_params.get("msg", "")

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "message": msg}
    )

@app.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    email = login_data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()
    if not user or not auth.verify_password(login_data.password, user.password):
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    if not user.is_active:
        return JSONResponse({"error": "Your account has been blocked by admin"}, status_code=403)
    response = JSONResponse({"message": "Login successful", "redirect": get_role_dashboard(user.role)})
    response.set_cookie("user_email", email,     httponly=True, samesite="lax", path="/")
    response.set_cookie("user_role",  user.role, httponly=True, samesite="lax", path="/")
    return response


@app.get("/logout")
@app.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("user_email")
    response.delete_cookie("user_role")
    return response


# ─────────────────────────────────────────────────────────────────────────────
#  FORGOT PASSWORD
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse( "forgot_password.html", {"request": request})


@app.post("/forgot-password")
def forgot_password(data: ForgotPassword, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"message": "If that email exists, an OTP has been sent."})

    otp = str(random.randint(100000, 999999))

    # ✅ FIX (store datetime, NOT string)
    otp_expiry = datetime.utcnow() + timedelta(minutes=5)

    user.otp = otp
    user.otp_expiry = otp_expiry
    db.commit()

    print("OTP:", otp)  # 👈 debug

    if not send_email(email, otp):
        return JSONResponse({"error": "Email failed"}, status_code=500)

    return JSONResponse({"message": "OTP sent"})


@app.post("/verify-otp")
def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)

    if not user.otp or not user.otp_expiry:
        return JSONResponse({"error": "No OTP found"}, status_code=400)

    # ✅ FIX (no fromisoformat)
    if datetime.utcnow() > user.otp_expiry:
        user.otp = None
        user.otp_expiry = None
        db.commit()
        return JSONResponse({"error": "OTP expired"}, status_code=400)

    if user.otp != data.otp:
        return JSONResponse({"error": "Invalid OTP"}, status_code=400)

    user.otp = "VERIFIED"
    db.commit()

    return JSONResponse({"message": "OTP verified"})


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    return templates.TemplateResponse( "reset_password.html", {"request": request})


@app.post("/reset-password")
def reset_password(data: ResetPassword, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)

    # ✅ FIX (safe check)
    if not user.otp or user.otp != "VERIFIED":
        return JSONResponse({"error": "OTP not verified"}, status_code=403)

    user.password = auth.hash_password(data.new_password)

    # clear OTP
    user.otp = None
    user.otp_expiry = None

    db.commit()

    return JSONResponse({"message": "Password reset successful"})

# ─────────────────────────────────────────────────────────────────────────────
#  DASHBOARDS
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "user")
    if err:
        return err
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user}
    )

@app.get("/super-admin/dashboard", response_class=HTMLResponse)
def super_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    return templates.TemplateResponse(
        "super_admin_dashboard.html",
        {"request": request, "user": user}
    )

@app.get("/super-admin/users", response_class=HTMLResponse)
def view_users(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err

    search = request.query_params.get("search", "").strip()
    q = db.query(models.User)

    if search:
        q = q.filter(models.User.email.contains(search))

    return templates.TemplateResponse(
        "manage_users.html",
        {
            "request": request,
            "users": q.all(),
            "user": user,
            "search": search
        }
    )
@app.get("/super-admin/users-json")
def get_users_json(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    search = request.query_params.get("search", "").strip()
    q = db.query(models.User)
    if search:
        q = q.filter(models.User.email.contains(search))
    return [{"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active}
            for u in q.all()]


@app.get("/super-admin/stats")
def get_stats(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {
        "total":       db.query(models.User).count(),
        "admins":      db.query(models.User).filter(models.User.role == "clientadmin").count(),
        "superadmins": db.query(models.User).filter(models.User.role == "superadmin").count(),
    }


@app.post("/super-admin/toggle-user/{user_id}")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.id == user.id:
        return JSONResponse({"error": "Cannot block yourself"}, status_code=400)
    target.is_active = not target.is_active
    db.commit()
    db.refresh(target)
    return JSONResponse({"success": True, "is_active": target.is_active})


@app.post("/super-admin/update-email/{user_id}")
def update_email(user_id: int, payload: EmailUpdate, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    new_email = payload.email.strip().lower()
    if not new_email:
        return JSONResponse({"error": "Email required"}, status_code=400)
    dup = db.query(models.User).filter(models.User.email == new_email).first()
    if dup and dup.id != user_id:
        return JSONResponse({"error": "Email already in use"}, status_code=400)
    target.email = new_email
    db.commit()
    return JSONResponse({"success": True})


@app.post("/super-admin/update-role/{user_id}")
def update_role(user_id: int, data: UpdateRoleBody, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.role == "superadmin":
        return JSONResponse({"error": "Cannot change a Super Admin's role"}, status_code=403)
    target.role = data.role
    db.commit()
    return JSONResponse({"success": True})


@app.post("/super-admin/delete-user/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.id == user.id:
        return JSONResponse({"error": "Cannot delete yourself"}, status_code=400)
    if target.role == "superadmin":
        return JSONResponse({"error": "Cannot delete another superadmin"}, status_code=403)
    db.delete(target)
    db.commit()
    return JSONResponse({"success": True})


@app.get("/super-admin/users", response_class=HTMLResponse)
def view_users(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err

    search = request.query_params.get("search", "").strip()
    q = db.query(models.User)

    if search:
        q = q.filter(models.User.email.contains(search))

    return templates.TemplateResponse(
        "manage_users.html",
        {
            "request": request,
            "users": q.all(),
            "user": user,
            "search": search
        }
    )

@app.get("/client-admin/users-json")
def get_users_client(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    users = db.query(models.User).filter(models.User.role == "user").all()
    return [{"id": u.id, "email": u.email, "is_active": u.is_active} for u in users]


@app.post("/client-admin/toggle-user/{user_id}")
def toggle_user_client(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)
    target.is_active = not target.is_active
    db.commit()
    db.refresh(target)
    return JSONResponse({"success": True, "is_active": target.is_active})


@app.post("/client-admin/delete-user/{user_id}")
def delete_user_client(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)
    db.delete(target)
    db.commit()
    return JSONResponse({"success": True})


@app.post("/client-admin/update-email/{user_id}")
def update_email_client(user_id: int, payload: EmailUpdate, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)
    new_email = payload.email.strip().lower()
    if not new_email:
        return JSONResponse({"error": "Email required"}, status_code=400)
    dup = db.query(models.User).filter(models.User.email == new_email).first()
    if dup and dup.id != user_id:
        return JSONResponse({"error": "Email already in use"}, status_code=400)
    target.email = new_email
    db.commit()
    db.refresh(target)
    return JSONResponse({"success": True, "email": target.email})