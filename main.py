"""
Blog Management System - Main Application
==========================================
Sections:
  1. Imports & Config
  2. Helper Classes (Pydantic Models)
  3. Helper Functions
  4. Exception Handlers
  5. Public Routes (Home, Blogs API)
  6. Auth Routes (Register, Login, Logout, Forgot/Reset Password)
  7. User Dashboard Routes
  8. Super Admin Routes
  9. Super Admin Blog Management
  10. Client Admin Routes
  11. Client Admin Blog Management
"""

# ================================================================
# 1. IMPORTS & CONFIG
# ================================================================

import os
import re
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from blog_router import router as blog_router
from dependencies import AuthenticationError, AdminPermissionError
import auth
import models
from models import Blog, User
from database import sessionlocal, engine
from blog_schemas import BlogCreate

# Initialize database tables
models.Base.metadata.create_all(bind=engine)
load_dotenv()

# App setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

app = FastAPI(title="Blog Management System")
app.include_router(blog_router)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Email config
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "harshitjangid99291@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "ykjlxoqtzmcfnbog")


# ================================================================
# 2. HELPER CLASSES (Pydantic Models)
# ================================================================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone: str | None = None
    gender: str | None = None

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
    email: EmailStr
    password: str


class ForgotPassword(BaseModel):
    email: EmailStr


class VerifyOTP(BaseModel):
    email: EmailStr
    otp: str


class ResetPassword(BaseModel):
    email: EmailStr
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


# ================================================================
# 3. HELPER FUNCTIONS
# ================================================================

def get_db():
    """Database session dependency."""
    db = sessionlocal()
    try:
        yield db
    finally:
        db.close()


def get_role_dashboard(role: str) -> str:
    """Get dashboard URL based on user role."""
    return {
        "superadmin": "/super-admin/dashboard",
        "clientadmin": "/client-admin/dashboard",
    }.get(role, "/dashboard")


def require_role(request: Request, db: Session, role: str, is_api: bool = False):
    """Check if user has required role. Returns (user, None) or (None, error_response)."""
    email = request.cookies.get("user_email")

    if not email:
        if is_api:
            return None, JSONResponse({"error": "Please login first"}, status_code=401)
        return None, RedirectResponse("/login?msg=Please login first", status_code=303)

    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or not user.is_active:
        if is_api:
            return None, JSONResponse({"error": "Account blocked or invalid"}, status_code=401)
        return None, RedirectResponse("/login?msg=Account blocked or invalid", status_code=303)

    if user.role != role:
        if is_api:
            return None, JSONResponse({"error": "Permission denied"}, status_code=403)
        return None, RedirectResponse(get_role_dashboard(user.role), status_code=303)

    return user, None


def get_current_user(request: Request, db: Session):
    """Get currently logged in user from cookies."""
    email = request.cookies.get("user_email")
    if not email:
        return None
    return db.query(models.User).filter(models.User.email == email).first()


def send_email(to_email: str, otp: str) -> tuple[bool, str]:
    """Send OTP email."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your OTP Code - {otp}"
        msg["From"] = f"Blog Management <{SENDER_EMAIL}>"
        msg["To"] = to_email

        text = f"Your OTP code is: {otp}\nExpires in 5 minutes."
        html = f"""
        <html>
        <body style="font-family:Arial,sans-serif;padding:20px;">
            <div style="max-width:400px;margin:0 auto;background:#f4f4f4;padding:30px;border-radius:12px;text-align:center;">
                <h2 style="color:#667eea;">Blog Management</h2>
                <p style="font-size:16px;">Your OTP code is:</p>
                <h1 style="color:#764ba2;letter-spacing:8px;font-size:40px;margin:20px 0;">{otp}</h1>
                <p style="color:#888;font-size:13px;">This code expires in 5 minutes.<br>Do not share this with anyone.</p>
                <hr style="border:none;border-top:1px solid #ddd;margin:20px 0;">
                <p style="color:#aaa;font-size:11px;">If you didn't request this, ignore this email.</p>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()
        print(f"✅ Email sent to {to_email}")
        return True, ""
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False, str(e)


# ================================================================
# 4. EXCEPTION HANDLERS
# ================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [e["msg"].replace("Value error, ", "") for e in exc.errors()]
    return JSONResponse(status_code=400, content={"error": "\n".join(errors)})


@app.exception_handler(AuthenticationError)
async def auth_exception_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(AdminPermissionError)
async def admin_exception_handler(request: Request, exc: AdminPermissionError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


# ================================================================
# 5. PUBLIC ROUTES (Home, Blogs API)
# ================================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Home page - shows all blogs publicly."""
    return templates.TemplateResponse(request, "home.html", {"request": request})


@app.get("/blogs")
def get_blogs(db: Session = Depends(get_db)):
    """API: Get all blogs (public, no login required)."""
    blogs = db.query(Blog).all()
    result = []
    for b in blogs:
        owner = db.query(User).filter(User.id == b.user_id).first()
        result.append({
            "id": b.id,
            "title": b.title,
            "description": b.description,
            "content": b.content,
            "owner_email": owner.email if owner else "Unknown",
            "owner_role": owner.role if owner else "Unknown",
            "created_at": b.created_at.isoformat() if b.created_at else None
        })
    return result


@app.get("/blog/{blog_id}")
def view_blog_api(blog_id: int, db: Session = Depends(get_db)):
    """API: Get single blog details (public, no login required)."""
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        return JSONResponse({"error": "Blog not found"}, status_code=404)
    owner = db.query(models.User).filter(models.User.id == blog.user_id).first()
    return {
        "id": blog.id,
        "title": blog.title,
        "description": blog.description,
        "content": blog.content,
        "owner_email": owner.email if owner else "Unknown",
        "created_at": blog.created_at
    }


@app.get("/blog/view/{blog_id}", response_class=HTMLResponse)
def view_blog_page(blog_id: str, request: Request, db: Session = Depends(get_db)):
    """Page: View blog detail page (login required)."""
    try:
        blog_id = int(blog_id)
    except ValueError:
        return JSONResponse({"error": "Invalid blog ID"}, status_code=400)

    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)

    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        return HTMLResponse("Blog not found.", status_code=404)

    # Permission check
    if user.role == "user" and blog.user_id != user.id:
        return HTMLResponse("You do not have permission to view this blog.", status_code=403)

    if user.role == "clientadmin":
        blog_owner = db.query(models.User).filter(models.User.id == blog.user_id).first()
        if blog_owner and blog_owner.role not in ("user", "clientadmin"):
            return HTMLResponse("You do not have permission to view this blog.", status_code=403)

    owner = db.query(models.User).filter(models.User.id == blog.user_id).first()
    return templates.TemplateResponse(request, "view_blog.html", {
        "request": request,
        "blog": blog,
        "owner_email": owner.email if owner else "Unknown",
        "user": user
    })


@app.delete("/blogs/{blog_id}")
def delete_blog(blog_id: int, request: Request, db: Session = Depends(get_db)):
    """API: Delete blog (owner or superadmin only)."""
    user = get_current_user(request, db)
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        return JSONResponse({"error": "Blog not found"}, status_code=404)

    if blog.user_id != user.id and user.role != "superadmin":
        return JSONResponse({"error": "Permission denied"}, status_code=403)

    db.delete(blog)
    db.commit()
    return JSONResponse({"message": "Blog deleted"})


# ================================================================
# 6. AUTH ROUTES (Register, Login, Logout, Forgot/Reset Password)
# ================================================================

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    if request.cookies.get("user_email"):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "register.html", {"request": request})


@app.post("/register")
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing:
        return JSONResponse({"error": "Email already registered"}, status_code=400)

    new_user = models.User(
        email=user_data.email,
        password=auth.hash_password(user_data.password),
        phone=user_data.phone,
        gender=user_data.gender,
        role="user",
    )
    db.add(new_user)
    db.commit()
    return JSONResponse({"message": "Registration successful! Please login."}, status_code=201)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    email = request.cookies.get("user_email")
    role = request.cookies.get("user_role")
    if email:
        return RedirectResponse(get_role_dashboard(role or "user"), status_code=303)
    msg = request.query_params.get("msg", "")
    return templates.TemplateResponse(request, "login.html", {
        "request": request, "name": "Harshit", "message": msg
    })


@app.post("/login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    email = login_data.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user or not auth.verify_password(login_data.password, user.password):
        return JSONResponse({"error": "Invalid credentials"}, status_code=401)
    if not user.is_active:
        return JSONResponse({"error": "Account blocked"}, status_code=403)

    redirect_url = get_role_dashboard(user.role)
    response = JSONResponse({"message": "Login successful", "redirect": redirect_url})
    response.set_cookie("user_email", email, httponly=True)
    response.set_cookie("user_role", user.role, httponly=True)
    return response


@app.get("/logout")
@app.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("user_email")
    response.delete_cookie("user_role")
    return response


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(request, "forgot_password.html", {"request": request})


@app.post("/forgot-password")
def forgot_password(data: ForgotPassword, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"message": "If that email exists, an OTP has been sent."})

    otp = str(random.randint(100000, 999999))
    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    db.commit()

    print(f"\n{'='*40}\n  OTP for {email}: {otp}\n{'='*40}\n")

    try:
        success, error_msg = send_email(email, otp)
        if not success:
            print(f"⚠️ Email failed: {error_msg}\n👉 Use OTP from terminal: {otp}")
    except Exception as e:
        print(f"⚠️ Email error: {e}\n👉 Use OTP from terminal: {otp}")

    return JSONResponse({"message": "OTP sent! Check your email (or terminal)"})


@app.post("/verify-otp")
def verify_otp(data: VerifyOTP, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if not user.otp or not user.otp_expiry:
        return JSONResponse({"error": "No OTP found"}, status_code=400)

    expiry = user.otp_expiry
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry)

    if datetime.utcnow() > expiry:
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
    return templates.TemplateResponse(request, "reset_password.html", {"request": request})


@app.post("/reset-password")
def reset_password(data: ResetPassword, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()

    if not user:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if not user.otp or user.otp != "VERIFIED":
        return JSONResponse({"error": "OTP not verified"}, status_code=403)

    user.password = auth.hash_password(data.new_password)
    user.otp = None
    user.otp_expiry = None
    db.commit()
    return JSONResponse({"message": "Password reset successful"})


# ================================================================
# 7. USER DASHBOARD ROUTES
# ================================================================

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    """User dashboard - shows user's own blogs."""
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    blogs = db.query(models.Blog).filter(models.Blog.user_id == user.id).all()
    return templates.TemplateResponse(request, "dashboard.html", {
        "request": request, "user": user, "blogs": blogs
    })


@app.get("/create-blog", response_class=HTMLResponse)
def create_blog_page(request: Request):
    """Page: Create blog form for regular users."""
    return templates.TemplateResponse(request, "create_blog.html", {"request": request})


@app.post("/create-blog")
async def create_blog(request: Request, blog_data: BlogCreate, db: Session = Depends(get_db)):
    """API: Create blog for regular users."""
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")

    new_blog = models.Blog(
        title=blog_data.title,
        description=blog_data.description,
        content=blog_data.content,
        user_id=user.id
    )
    db.add(new_blog)
    db.commit()
    db.refresh(new_blog)
    return {"message": "Blog created successfully", "blog_id": new_blog.id}


# ================================================================
# 8. SUPER ADMIN ROUTES
# ================================================================

# --- Dashboard ---

@app.get("/super-admin/dashboard", response_class=HTMLResponse)
def super_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    return templates.TemplateResponse(request, "super_admin_dashboard.html", {
        "request": request, "user": user
    })


@app.get("/super-admin/stats")
def get_stats(request: Request, db: Session = Depends(get_db)):
    """API: Get stats for super admin dashboard."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
    return {
        "total": db.query(models.User).count(),
        "admins": db.query(models.User).filter(models.User.role == "clientadmin").count(),
        "superadmins": db.query(models.User).filter(models.User.role == "superadmin").count(),
    }


# --- User Management ---

@app.get("/super-admin/users", response_class=HTMLResponse)
def view_users(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    search = request.query_params.get("search", "").strip()
    q = db.query(models.User)
    if search:
        q = q.filter(models.User.email.contains(search))
    return templates.TemplateResponse(request, "manage_users.html", {
        "request": request, "users": q.all(), "user": user, "search": search
    })


@app.get("/super-admin/users-json")
def get_users_json(request: Request, db: Session = Depends(get_db)):
    """API: Get all users as JSON."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
    search = request.query_params.get("search", "").strip()
    q = db.query(models.User)
    if search:
        q = q.filter(models.User.email.contains(search))
    return [{"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active} for u in q.all()]


@app.post("/super-admin/toggle-user/{user_id}")
def toggle_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    """API: Block/Unblock user."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
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
    """API: Update user email."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
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
    """API: Update user role."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        return JSONResponse({"error": "User not found"}, status_code=404)
    if target.id == user.id:
        return JSONResponse({"error": "You cannot change your own role"}, status_code=400)
    if target.role == "superadmin":
        return JSONResponse({"error": "Superadmin role is permanent and cannot be changed!"}, status_code=403)

    new_role = data.role.strip().lower()
    if new_role not in ["user", "clientadmin"]:
        return JSONResponse({"error": "Invalid role"}, status_code=400)

    target.role = new_role
    db.commit()
    db.refresh(target)
    return JSONResponse({"success": True, "new_role": target.role})


@app.post("/super-admin/delete-user/{user_id}")
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db)):
    """API: Delete user."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
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


# ================================================================
# 9. SUPER ADMIN BLOG MANAGEMENT
# ================================================================

@app.get("/super-admin/blogs", response_class=HTMLResponse)
def super_admin_blogs(request: Request, db: Session = Depends(get_db)):
    """Page: View all users' blogs."""
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    users = db.query(models.User).all()
    data = []
    for u in users:
        blogs = db.query(models.Blog).filter(models.Blog.user_id == u.id).all()
        data.append({
            "user_id": u.id,
            "email": u.email,
            "blog_count": len(blogs),
            "blogs": [{"id": b.id, "title": b.title, "created_at": b.created_at} for b in blogs]
        })
    return templates.TemplateResponse(request, "super_admin_blogs.html", {
        "request": request, "data": data, "user": user
    })


@app.delete("/super-admin/blogs/{blog_id}")
def super_admin_delete_blog(blog_id: int, request: Request, db: Session = Depends(get_db)):
    """API: Delete any blog (super admin)."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        return JSONResponse({"error": "Blog not found"}, status_code=404)
    db.delete(blog)
    db.commit()
    return JSONResponse({"message": "Blog deleted"})


@app.get("/super-admin/blog-status", response_class=HTMLResponse)
def super_admin_blog_status(request: Request, db: Session = Depends(get_db)):
    """Page: Blog creation status for all users."""
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    users = db.query(models.User).all()
    data = []
    for u in users:
        blog = db.query(models.Blog).filter(models.Blog.user_id == u.id).first()
        data.append({
            "email": u.email,
            "status": "Created" if blog else "Not Created",
            "title": blog.title if blog else "-",
            "time": blog.created_at if blog else None,
            "user_id": u.id,
            "blog_id": blog.id if blog else None,
            "has_blog": True if blog else False
        })
    return templates.TemplateResponse(request, "super_admin_blog_status.html", {
        "request": request, "data": data, "user": user
    })


@app.get("/super-admin/create-blog", response_class=HTMLResponse)
def super_admin_create_blog_page(request: Request, db: Session = Depends(get_db)):
    """Page: Create blog form for super admin."""
    user, err = require_role(request, db, "superadmin")
    if err:
        return err
    return templates.TemplateResponse(request, "admin_create_blog.html", {
        "request": request,
        "user": user,
        "back_url": "/super-admin/dashboard",
        "post_url": "/super-admin/create-blog"
    })


@app.post("/super-admin/create-blog")
def super_admin_create_blog(request: Request, blog_data: BlogCreate, db: Session = Depends(get_db)):
    """API: Create blog as super admin."""
    user, err = require_role(request, db, "superadmin", is_api=True)
    if err:
        return err
    new_blog = models.Blog(
        title=blog_data.title,
        description=blog_data.description,
        content=blog_data.content,
        user_id=user.id
    )
    db.add(new_blog)
    db.commit()
    db.refresh(new_blog)
    return {"message": "Blog created successfully", "blog_id": new_blog.id}


# ================================================================
# 10. CLIENT ADMIN ROUTES
# ================================================================

# --- Dashboard ---

@app.get("/client-admin/dashboard", response_class=HTMLResponse)
def client_admin_dashboard(request: Request, db: Session = Depends(get_db)):
    user, err = require_role(request, db, "clientadmin")
    if err:
        return err
    return templates.TemplateResponse(request, "client_admin_dashboard.html", {
        "request": request, "user": user
    })


@app.get("/client-admin/stats")
def get_client_stats(request: Request, db: Session = Depends(get_db)):
    """API: Get stats for client admin dashboard."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err

    total_users = db.query(models.User).filter(models.User.role == "user").count()

    # Count blogs of users + client admin's own blogs
    user_ids = [u.id for u in db.query(models.User).filter(models.User.role == "user").all()]
    user_ids.append(user.id)
    total_blogs = db.query(models.Blog).filter(models.Blog.user_id.in_(user_ids)).count()
    my_blogs = db.query(models.Blog).filter(models.Blog.user_id == user.id).count()

    return {
        "total_users": total_users,
        "total_blogs": total_blogs,
        "my_blogs": my_blogs
    }


@app.get("/client-admin/my-blogs-json")
def get_client_my_blogs(request: Request, db: Session = Depends(get_db)):
    """API: Get client admin's own blogs."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err
    blogs = db.query(models.Blog).filter(models.Blog.user_id == user.id).all()
    return [{
        "id": b.id,
        "title": b.title,
        "description": b.description,
        "created_at": b.created_at.isoformat() if b.created_at else None
    } for b in blogs]


@app.get("/client-admin/all-blogs-json")
def get_client_all_blogs(request: Request, db: Session = Depends(get_db)):
    """API: Get all blogs (users + client admin's own)."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err

    user_ids = [u.id for u in db.query(models.User).filter(models.User.role == "user").all()]
    user_ids.append(user.id)

    blogs = db.query(models.Blog).filter(models.Blog.user_id.in_(user_ids)).all()
    result = []
    for b in blogs:
        owner = db.query(models.User).filter(models.User.id == b.user_id).first()
        result.append({
            "id": b.id,
            "title": b.title,
            "description": b.description,
            "owner_email": owner.email if owner else "Unknown",
            "created_at": b.created_at.isoformat() if b.created_at else None
        })
    return result


# --- User Management ---

@app.get("/client-admin/users-json")
def get_users_client(request: Request, db: Session = Depends(get_db)):
    """API: Get users with role 'user' only."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err
    search = request.query_params.get("search", "").strip()
    q = db.query(models.User).filter(models.User.role == "user")
    if search:
        q = q.filter(models.User.email.contains(search))
    return [{"id": u.id, "email": u.email, "is_active": u.is_active} for u in q.all()]


@app.post("/client-admin/toggle-user/{user_id}")
def toggle_user_client(user_id: int, request: Request, db: Session = Depends(get_db)):
    """API: Block/Unblock user (client admin)."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err
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
    """API: Delete user (client admin, only role='user')."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err
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
    """API: Update user email (client admin)."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err
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


# ================================================================
# 11. CLIENT ADMIN BLOG MANAGEMENT
# ================================================================

@app.get("/client-admin/blogs", response_class=HTMLResponse)
def client_admin_blogs(request: Request, db: Session = Depends(get_db)):
    """Page: View all users' blogs (client admin)."""
    user, err = require_role(request, db, "clientadmin")
    if err:
        return err
    users = db.query(models.User).filter(models.User.role == "user").all()
    data = []
    for u in users:
        blogs = db.query(models.Blog).filter(models.Blog.user_id == u.id).all()
        data.append({
            "user_id": u.id,
            "email": u.email,
            "blog_count": len(blogs),
            "blogs": [{"id": b.id, "title": b.title, "created_at": b.created_at} for b in blogs]
        })
    return templates.TemplateResponse(request, "client_admin_blogs.html", {
        "request": request, "data": data, "user": user
    })


@app.delete("/client-admin/blogs/{blog_id}")
def client_admin_delete_blog(blog_id: int, request: Request, db: Session = Depends(get_db)):
    """API: Delete blog (client admin - own blogs + user role blogs)."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err

    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        return JSONResponse({"error": "Blog not found"}, status_code=404)

    # Allow deleting OWN blogs
    if blog.user_id == user.id:
        db.delete(blog)
        db.commit()
        return JSONResponse({"message": "Blog deleted"})

    # Allow deleting blogs of "user" role only
    owner = db.query(models.User).filter(models.User.id == blog.user_id).first()
    if not owner or owner.role != "user":
        return JSONResponse({"error": "Not allowed"}, status_code=403)

    db.delete(blog)
    db.commit()
    return JSONResponse({"message": "Blog deleted"})


@app.get("/client-admin/blog-status", response_class=HTMLResponse)
def client_blog_status(request: Request, db: Session = Depends(get_db)):
    """Page: Blog creation status for users (client admin)."""
    user, err = require_role(request, db, "clientadmin")
    if err:
        return err
    users = db.query(models.User).filter(models.User.role == "user").all()
    data = []
    for u in users:
        blog = db.query(models.Blog).filter(models.Blog.user_id == u.id).first()
        data.append({
            "email": u.email,
            "status": "Created" if blog else "Not Created",
            "title": blog.title if blog else "-",
            "time": blog.created_at if blog else None,
            "user_id": u.id,
            "blog_id": blog.id if blog else None,
            "has_blog": True if blog else False
        })
    return templates.TemplateResponse(request, "client_blog_status.html", {
        "request": request, "data": data, "user": user
    })


@app.get("/client-admin/create-blog", response_class=HTMLResponse)
def client_admin_create_blog_page(request: Request, db: Session = Depends(get_db)):
    """Page: Create blog form for client admin."""
    user, err = require_role(request, db, "clientadmin")
    if err:
        return err
    return templates.TemplateResponse(request, "admin_create_blog.html", {
        "request": request,
        "user": user,
        "back_url": "/client-admin/dashboard",
        "post_url": "/client-admin/create-blog"
    })


@app.post("/client-admin/create-blog")
def client_admin_create_blog(request: Request, blog_data: BlogCreate, db: Session = Depends(get_db)):
    """API: Create blog as client admin."""
    user, err = require_role(request, db, "clientadmin", is_api=True)
    if err:
        return err
    new_blog = models.Blog(
        title=blog_data.title,
        description=blog_data.description,
        content=blog_data.content,
        user_id=user.id
    )
    db.add(new_blog)
    db.commit()
    db.refresh(new_blog)
    return {"message": "Blog created successfully", "blog_id": new_blog.id}