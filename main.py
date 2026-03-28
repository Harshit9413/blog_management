import os
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
import smtplib
import re
import auth
import models
from database import sessionlocal, engine

models.Base.metadata.create_all(bind=engine)
load_dotenv()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
print("....", os.path.join(BASE_DIR, "templates"))
app = FastAPI()

def send_email(to_email, otp):
    sender   = "harshitjangid99291@gmail.com"
    password = "cqijkpmkflgowpky"

    html_content = f"""
    <!DOCTYPE html>
    <html><head><meta charset="UTF-8"></head>
    <body style="background:#0d1117;font-family:Arial;padding:40px;color:#fff;">
      <div style="max-width:500px;margin:auto;background:#111827;border-radius:16px;padding:40px;border:1px solid #2d6a3f;">
        <h2 style="color:#4ade80;text-align:center;">🛡️ OTP Verification</h2>
        <p style="color:#9ca3af;">Your verification code is:</p>
        <div style="text-align:center;margin:30px 0;">
          <span style="font-size:42px;font-weight:800;letter-spacing:12px;color:#fff;font-family:monospace;">{otp}</span>
        </div>
        <p style="color:#9ca3af;font-size:13px;">This code expires in <strong style="color:#4ade80;">5 minutes</strong>.</p>
        <p style="color:#6b7280;font-size:11px;margin-top:30px;">If you didn't request this, ignore this email.</p>
      </div>
    </body></html>
    """

    msg             = MIMEText(html_content, "html")
    msg["From"]     = sender
    msg["To"]       = to_email
    msg["Subject"]  = "Your OTP Code"

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender, password)
        server.sendmail(sender, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent")
    except Exception as e:
        print(f"❌ Email error: {e}")

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
            raise ValueError("Invalid phone number (must be 10 digits and start with 6-9)")
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

ROLE_LEVELS = {
    "user": 1,
    "clientadmin": 2,
    "superadmin": 3
}
class ForgotPassword(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp:   str

class UpdateRoleBody(BaseModel):
    role: str
    

    @field_validator("role")
    def validate_role(cls, value):
        allowed = {"user", "clientadmin", "superadmin"}
        if value not in allowed:
            raise ValueError(f"Role must be one of: {', '.join(allowed)}")
        return value
class EmailUpdate(BaseModel):
    email: str

class ResetPassword(BaseModel):
    email:        EmailStr
    new_password: str

    @field_validator("new_password")
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not re.search(r"\d", value):
            raise ValueError("Password must contain a number")
        return value

def get_db():
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()

def get_role_dashboard(role: str) -> str:
    if role == "superadmin":
        return "/super-admin/dashboard"
    elif role == "clientadmin":
        return "/client-admin/dashboard"
    else:
        return "/dashboard"

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
    errors = [err["msg"].replace("Value error, ", "") for err in exc.errors()]
    return JSONResponse(status_code=400, content={"error": "\n".join(errors)})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    user_email = request.cookies.get("user_email")
    if user_email:
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
    
    user_email = request.cookies.get("user_email")
    user_role  = request.cookies.get("user_role")

    if user_email:
        if user_role == "superadmin":
            return RedirectResponse("/super-admin/dashboard", status_code=303)
        elif user_role == "clientadmin":
            return RedirectResponse("/client-admin/dashboard", status_code=303)
        else:
            return RedirectResponse("/dashboard", status_code=303)
    
    msg = request.query_params.get("msg", "")
    print()
    
    #return templates.TemplateResponse("login.html", {"request": request, "message": msg})
    return templates.TemplateResponse(
        request,
        "login.html",
        {"message": msg}
    )

@app.post("/login")
def login(request: Request, login_data: UserLogin, db: Session = Depends(get_db)):
    email    = login_data.email.strip().lower()
    password = login_data.password

    print(f"🔍 Login attempt: {email}")

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        print("❌ User not found")
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    if not auth.verify_password(password, user.password):
        print("❌ Password mismatch")
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)

    if not user.is_active:
        print("🚫 Blocked user tried to login")
        return JSONResponse(
            {"error": "Your account is blocked by admin"},
            status_code=403
        )
    if user.role == "superadmin":
        redirect_url = "/super-admin/dashboard"
    elif user.role == "clientadmin":
        redirect_url = "/client-admin/dashboard"
    else:
        redirect_url = "/dashboard"

    print(f"✅ Login success → {redirect_url}")

    response = JSONResponse({
        "message": "Login successful",
        "redirect": redirect_url
    })
    response.set_cookie(
        key="user_email",
        value=email,
        httponly=True,
        samesite="lax",
        path="/"
    )

    response.set_cookie(
        key="user_role",
        value=user.role,
        httponly=True,
        samesite="lax",
        path="/"
    )

    return response

    
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "user")
    if err:
        return err  
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})


@app.get("/super-admin/dashboard", response_class=HTMLResponse)
def super_admin_dashboard(request: Request, db: Session = Depends(get_db)):

    user, err = require_role(request, db, "superadmin")

    if err:
        return err
       
    return templates.TemplateResponse("super_admin_dashboard.html", {
        "request": request,
        "user": user
    })
@app.get("/super-admin/users", response_class=HTMLResponse)
def view_users(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err

    search = request.query_params.get("search")

    if search:
        users = db.query(models.User).filter(
            models.User.email.contains(search)
        ).all()
    else:
        users = db.query(models.User).all()

    return templates.TemplateResponse(
        "manage_users.html",
        {"request": request, "users": users, "user": user, "search": search}
    )
@app.get("/super-admin/users-json")
def get_users_json(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err

    search = request.query_params.get("search")

    if search:
        users = db.query(models.User).filter(models.User.email.contains(search)).all()
    else:
        users = db.query(models.User).all()

    return [
        {
            "id":        u.id,
            "email":     u.email,
            "role":      u.role,
            "is_active": u.is_active
        }
        for u in users
    ]
@app.get("/super-admin/stats")
def get_stats(request:Request,db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")

    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    total_users = db.query(models.User).count()
    admins = db.query(models.User).filter(models.User.role == "clientadmin").count()
    superadmins = db.query(models.User).filter(models.User.role == "superadmin").count()

    return {
        "total": total_users,
        "admins": admins,
        "superadmins": superadmins
    }   

@app.post("/super-admin/toggle-user/{user_id}")
def toggle_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    # prevent self block
    if target.id == user.id:
        return JSONResponse({"error": "You cannot block yourself"}, status_code=400)

    target.is_active = not target.is_active
    db.commit()
    db.refresh(target)

    return JSONResponse({
        "success": True,
        "is_active": target.is_active
    })

@app.post("/super-admin/update-email/{user_id}")
def update_email(
    user_id: int,
    payload: EmailUpdate,
    request: Request,
    db: Session = Depends(get_db)
):
    user, err = require_role(request, db, "superadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    target = db.query(models.User).filter(models.User.id == user_id).first()

    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    new_email = payload.email.strip().lower()

    if not new_email:
        return JSONResponse({"error": "Email required"}, status_code=400)

    # check duplicate
    existing = db.query(models.User).filter(models.User.email == new_email).first()
    if existing and existing.id != user_id:
        return JSONResponse({"error": "Email already exists"}, status_code=400)

    target.email = new_email
    db.commit()

    return {"success": True}
@app.post("/super-admin/update-role/{user_id}")
def update_role(user_id: int, data: dict, db: Session = Depends(get_db)):

    allowed_roles = ["user", "clientadmin"]

    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        return {"success": False, "error": "User not found"}

    # Protect superadmin
    if user.role == "superadmin":
        return {"success": False, "error": "Cannot modify Super Admin"}

    if data.get("role") not in allowed_roles:
        return {"success": False, "error": "Invalid role"}

    user.role = data["role"]
    db.commit()

    return {"success": True}

@app.post("/super-admin/delete-user/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):

    user, err = require_role(request, db, "superadmin")
    if err:
        return RedirectResponse("/login", status_code=303)

    target = db.query(models.User).filter(models.User.id == user_id).first()

    if not target:
        return RedirectResponse("/super-admin/dashboard?msg=User not found", status_code=303)

    if target.email == user.email:
        return RedirectResponse("/super-admin/dashboard?msg=Cannot delete yourself", status_code=303)

    db.delete(target)
    db.commit()

    # ✅ redirect back (IMPORTANT)
    return RedirectResponse("/super-admin/dashboard?msg=Deleted", status_code=303)

@app.get("/client-admin/dashboard", response_class=HTMLResponse)
def client_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return err

    # Fetch only normal users
    users = db.query(models.User).filter(models.User.role == "user").all()

    return templates.TemplateResponse(
        "client_admin_dashboard.html",
        {
            "request": request,
            "user": user,
            "users": users   # Pass users here
        }
    )
    
@app.get("/client-admin/users-json")
def get_users(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    users = db.query(models.User).filter(models.User.role == "user").all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "is_active": u.is_active
        }
        for u in users
    ]   

@app.post("/client-admin/toggle-user/{user_id}")
def toggle_users(user_id: int, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    # Only normal users
    if target.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)

    target.is_active = not target.is_active
    db.commit()
    db.refresh(target)

    return {"success": True, "is_active": target.is_active}

@app.post("/client-admin/delete-user/{user_id}")
def delete_user_client(user_id: int, request: Request, db: Session = Depends(get_db)):

    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    target = db.query(models.User).filter(models.User.id == user_id).first()

    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    # ✅ client admin can only delete normal users
    if target.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)

    db.delete(target)
    db.commit()

    return {"success": True}

@app.post("/client-admin/update-email/{user_id}")
def update_emails (user_id: int, data: dict, request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)

    if target.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)

    new_email = data.get("email", "").strip().lower()
    if not new_email:
        return JSONResponse({"error": "Email required"}, status_code=400)

    existing = db.query(models.User).filter(models.User.email == new_email).first()
    if existing and existing.id != user_id:
        return JSONResponse({"error": "Email already exists"}, status_code=400)

    target.email = new_email
    db.commit()
    db.refresh(target)

    return {"success": True, "email": target.email}
@app.post("/verify-otp")
def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user:
        return JSONResponse({"error": "User not found"}, status_code=400)
    if user.otp != data.otp:
        return JSONResponse({"error": "Invalid OTP"}, status_code=400)
    if datetime.utcnow() > datetime.fromisoformat(user.otp_expiry):
        return JSONResponse({"error": "OTP expired"}, status_code=400)

    user.otp        = None
    user.otp_expiry = None
    db.commit()
    return JSONResponse({"message": "OTP verified successfully"})

@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    return templates.TemplateResponse("reset_password.html", {"request": request})

@app.post("/reset-password")
def reset_password(request: Request, data: ResetPassword, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user  = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return JSONResponse({"error": "User not found"}, status_code=400)

    user.password = auth.hash_password(data.new_password)
    db.commit()
    return JSONResponse({"message": "Password updated successfully"})


@app.get("/password-updated", response_class=HTMLResponse)
def password_updated(request: Request):
    return templates.TemplateResponse(
        "success.html",
        {"request": request, "message": "Password updated successfully"}
    )

@app.post("/logout", response_class=HTMLResponse)
def logout(request: Request):
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("user_email")
    response.delete_cookie("user_role")
    return response

@app.get("/logout")
def logouut():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("user_email")
    response.delete_cookie("user_role")
    return response