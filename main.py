import os
import re
import smtplib
import random
from datetime import datetime, timedelta
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

# ── Startup ──────────────────────────────────────────────────────────────────
models.Base.metadata.create_all(bind=engine)
load_dotenv()

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
app       = FastAPI()


# ── Email helper ─────────────────────────────────────────────────────────────
SENDER_EMAIL    = os.getenv("SENDER_EMAIL", "harshitjangid99291@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "cqijkpmkflgowpky")   # use .env in production


def send_email(to_email: str, otp: str) -> bool:
    """Send OTP email. Returns True on success, False on failure."""
    html_content = f"""
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8"></head>
    <body style="background:#0d1117;font-family:Arial;padding:40px;color:#fff;">
      <div style="max-width:500px;margin:auto;background:#111827;border-radius:16px;
                  padding:40px;border:1px solid #2d6a3f;">
        <h2 style="color:#4ade80;text-align:center;">🛡️ OTP Verification</h2>
        <p style="color:#9ca3af;">Your password-reset code is:</p>
        <div style="text-align:center;margin:30px 0;">
          <span style="font-size:42px;font-weight:800;letter-spacing:12px;
                       color:#fff;font-family:monospace;">{otp}</span>
        </div>
        <p style="color:#9ca3af;font-size:13px;">
          Expires in <strong style="color:#4ade80;">5 minutes</strong>.
        </p>
        <p style="color:#6b7280;font-size:11px;margin-top:30px;">
          If you didn't request this, ignore this email.
        </p>
      </div>
    </body></html>
    """
    msg            = MIMEText(html_content, "html")
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = to_email
    msg["Subject"] = "Your OTP Code"

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent to", to_email)
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False


# ── Pydantic schemas ──────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email:    EmailStr
    password: str
    phone:    str | None = None
    gender:   str | None = None

    @field_validator("phone")
    def validate_phone(cls, value):
        if value is None or value == "":
            return value
        if not re.match(r"^[6-9]\d{9}$", value):
            raise ValueError("Invalid phone number (must be 10 digits, start with 6-9)")
        return value

    @field_validator("password")
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a number")
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must contain a letter")
        return value


class UserLogin(BaseModel):
    email:    EmailStr
    password: str

    @field_validator("password")
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters")
        return value


class ForgotPassword(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp:   str


class ResetPassword(BaseModel):
    email:        EmailStr
    new_password: str

    @field_validator("new_password")
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a number")
        if not re.search(r"[A-Za-z]", value):
            raise ValueError("Password must contain a letter")
        return value


class EmailUpdate(BaseModel):
    email: str


class UpdateRoleBody(BaseModel):
    role: str

    @field_validator("role")
    def validate_role(cls, value):
        allowed = {"user", "clientadmin", "superadmin"}
        if value not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return value


# ── DB dependency ─────────────────────────────────────────────────────────────
def get_db():
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()


# ── Role helpers ──────────────────────────────────────────────────────────────
def get_role_dashboard(role: str) -> str:
    return {
        "superadmin":  "/super-admin/dashboard",
        "clientadmin": "/client-admin/dashboard",
    }.get(role, "/dashboard")


def require_role(request: Request, db: Session, role: str):
    """
    Returns (user, None) on success or (None, RedirectResponse) on failure.
    """
    email = request.cookies.get("user_email")
    if not email:
        return None, RedirectResponse("/login?msg=Please login first", status_code=303)

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or not user.is_active:
        return None, RedirectResponse("/login?msg=Account blocked or invalid", status_code=303)

    if user.role != role:
        return None, RedirectResponse(get_role_dashboard(user.role), status_code=303)

    return user, None


# ── Global validation error handler ──────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [err["msg"].replace("Value error, ", "") for err in exc.errors()]
    return JSONResponse(status_code=400, content={"error": "\n".join(errors)})


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if request.cookies.get("user_email"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "register.html")


@app.post("/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing:
        return JSONResponse({"error": "Email already exists"}, status_code=400)

    new_user = models.User(
        email    = user_data.email,
        password = auth.hash_password(user_data.password),
        phone    = user_data.phone,
        gender   = user_data.gender,
        role     = "user",
    )
    db.add(new_user)
    db.commit()
    return JSONResponse({"message": "Account created successfully"})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    email = request.cookies.get("user_email")
    role  = request.cookies.get("user_role")
    if email:
        return RedirectResponse(get_role_dashboard(role or "user"), status_code=303)

    msg = request.query_params.get("msg", "")
    return templates.TemplateResponse(
        request, "login.html",
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

    redirect_url = get_role_dashboard(user.role)
    response = JSONResponse({"message": "Login successful", "redirect": redirect_url})
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


# ═══════════════════════════════════════════════════════════════════════════════
#  FORGOT PASSWORD  (3-step: request OTP → verify OTP → reset password)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    """Serve the forgot-password page (step 1 – enter email)."""
    return templates.TemplateResponse(request, "forgot_password.html", {"request": request})


@app.post("/forgot-password")
def forgot_password(data: ForgotPassword, db: Session = Depends(get_db)):
    """
    Step 1 – Validate email and send OTP.
    Returns 200 even if email not found to prevent user enumeration.
    """
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        # Generic success so attackers can't enumerate emails
        return JSONResponse({"message": "If that email exists, an OTP has been sent."})

    # Generate 6-digit OTP
    otp        = str(random.randint(100000, 999999))
    otp_expiry = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    user.otp        = otp
    user.otp_expiry = otp_expiry
    db.commit()

    sent = send_email(email, otp)
    if not sent:
        return JSONResponse(
            {"error": "Failed to send OTP. Please try again later."},
            status_code=500
        )

    return JSONResponse({"message": "OTP sent to your email."})


@app.post("/verify-otp")
def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    """
    Step 2 – Verify OTP.
    On success, marks otp_verified=True so the reset step is unlocked.
    """
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=400)

    if not user.otp:
        return JSONResponse({"error": "No OTP requested. Please request a new one."}, status_code=400)

    if user.otp != data.otp.strip():
        return JSONResponse({"error": "Invalid OTP"}, status_code=400)

    try:
        expiry = datetime.fromisoformat(user.otp_expiry)
    except (TypeError, ValueError):
        return JSONResponse({"error": "OTP data corrupted. Request a new one."}, status_code=400)

    if datetime.utcnow() > expiry:
        user.otp        = None
        user.otp_expiry = None
        db.commit()
        return JSONResponse({"error": "OTP has expired. Please request a new one."}, status_code=400)

    # Mark OTP as verified (clear the code but keep a flag) ─────────────────
    # We store a sentinel so the reset endpoint knows OTP was verified.
    # Using otp = "VERIFIED" is simple; use a DB boolean column if you prefer.
    user.otp = "VERIFIED"
    db.commit()

    return JSONResponse({"message": "OTP verified. You may now reset your password."})


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    """Serve the reset-password page (step 3 – enter new password)."""
    return templates.TemplateResponse(request, "reset_password.html", {"request": request})


@app.post("/reset-password")
def reset_password(data: ResetPassword, db: Session = Depends(get_db)):
    """
    Step 3 – Set new password.
    Only allowed if OTP was verified (user.otp == "VERIFIED").
    """
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=400)

    if user.otp != "VERIFIED":
        return JSONResponse(
            {"error": "OTP not verified. Please complete the OTP step first."},
            status_code=403
        )

    user.password   = auth.hash_password(data.new_password)
    user.otp        = None
    user.otp_expiry = None
    db.commit()

    return JSONResponse({"message": "Password reset successfully. You can now log in."})


@app.get("/password-updated", response_class=HTMLResponse)
def password_updated(request: Request):
    return templates.TemplateResponse(
        request, "success.html",
        {"request": request, "message": "Password updated successfully"}
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  USER DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "user")
    if err:
        return err
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


# ═══════════════════════════════════════════════════════════════════════════════
#  SUPER-ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/super-admin/dashboard", response_class=HTMLResponse)
def super_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    return templates.TemplateResponse(
        request, "super_admin_dashboard.html",
        {"request": request, "user": user}
    )


@app.get("/super-admin/users", response_class=HTMLResponse)
def view_users(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err

    search = request.query_params.get("search", "").strip()
    query  = db.query(models.User)
    if search:
        query = query.filter(models.User.email.contains(search))
    users = query.all()

    return templates.TemplateResponse(
        request, "manage_users.html",
        {"request": request, "users": users, "user": user, "search": search}
    )


@app.get("/super-admin/users-json")
def get_users_json(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    search = request.query_params.get("search", "").strip()
    query  = db.query(models.User)
    if search:
        query = query.filter(models.User.email.contains(search))

    return [
        {"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active}
        for u in query.all()
    ]


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
        return JSONResponse({"error": "You cannot block yourself"}, status_code=400)

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
        return JSONResponse({"error": "Email is required"}, status_code=400)

    existing = db.query(models.User).filter(models.User.email == new_email).first()
    if existing and existing.id != user_id:
        return JSONResponse({"error": "Email already in use"}, status_code=400)

    target.email = new_email
    db.commit()
    return JSONResponse({"success": True})


@app.post("/super-admin/update-role/{user_id}")
def update_role(user_id: int, data: UpdateRoleBody, request: Request, db: Session = Depends(get_db)):
    """
    FIX: Now requires auth, rejects superadmin promotion, and uses typed Pydantic model.
    """
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    if target.role == "superadmin":
        return JSONResponse({"error": "Cannot change a Super Admin's role"}, status_code=403)

    # Prevent assigning superadmin via this endpoint
    if data.role == "superadmin":
        return JSONResponse({"error": "Cannot promote to superadmin via this endpoint"}, status_code=403)

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
        return JSONResponse({"error": "You cannot delete yourself"}, status_code=400)
    if target.role == "superadmin":
        return JSONResponse({"error": "Cannot delete another superadmin"}, status_code=403)

    db.delete(target)
    db.commit()
    # FIX: return JSON instead of redirect (was mixing redirect with API calls)
    return JSONResponse({"success": True})


# ═══════════════════════════════════════════════════════════════════════════════
#  CLIENT-ADMIN ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/client-admin/dashboard", response_class=HTMLResponse)
def client_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return err

    users = db.query(models.User).filter(models.User.role == "user").all()
    return templates.TemplateResponse(
        request, "client_admin_dashboard.html",
        {"request": request, "user": user, "users": users}
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
    """FIX: Now uses typed EmailUpdate model instead of raw dict."""
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
        return JSONResponse({"error": "Email is required"}, status_code=400)

    existing = db.query(models.User).filter(models.User.email == new_email).first()
    if existing and existing.id != user_id:
        return JSONResponse({"error": "Email already in use"}, status_code=400)

    target.email = new_email
    db.commit()
    db.refresh(target)
    return JSONResponse({"success": True, "email": target.email})