import random
from datetime import datetime, timedelta
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against its hash."""
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError as e:
        print(f"❌ verify error: {e}")
        return False


def generate_otp() -> str:
    """Generate a 6-digit OTP string."""
    return f"{random.randint(100000, 999999)}"


def otp_expiry_time() -> datetime:
    """Return an OTP expiry timestamp 5 minutes from now."""
    return datetime.utcnow() + timedelta(minutes=5)