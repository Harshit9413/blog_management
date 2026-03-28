# auth.py
import random
from datetime import datetime, timedelta
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password"""
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify a plain password against a hash"""
    try:
        return pwd_context.verify(password, hashed)
    except ValueError as e:
        # Happens if the hash is malformed
        print(f"❌ verify error: {e}")
        return False

def generate_otp() -> str:
    """Generate a 6-digit OTP"""
    return f"{random.randint(100000, 999999)}"

def otp_expiry_time() -> datetime:
    """Return OTP expiry time (5 minutes from now)"""
    return datetime.utcnow() + timedelta(minutes=5)