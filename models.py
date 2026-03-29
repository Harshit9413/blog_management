from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from database import Base
class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True)
    email      = Column(String, unique=True, nullable=False)
    password   = Column(String, nullable=False)
    gender     = Column(String, nullable=True)
    phone      = Column(String, nullable=True)

    # ✅ OTP fields
    otp        = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)

    role       = Column(String, default="user")
    is_active  = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)