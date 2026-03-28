# models.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# ── Many-to-Many join table ──────────────────────────────────────
post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("tag_id",  Integer, ForeignKey("tags.id"),  primary_key=True),
)

# ── User (your existing model — unchanged) ───────────────────────
class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True)
    email      = Column(String, unique=True, nullable=False)
    password   = Column(String, nullable=False)
    gender     = Column(String, nullable=True)
    phone      = Column(String, nullable=True)
    otp        = Column(String, nullable=True)
    otp_expiry = Column(String, nullable=True)
    role       = Column(String, default="user")
    is_active  = Column(Boolean, default=True)
    last_login = Column(String, nullable=True)

    posts = relationship("Post", back_populates="author")

# ── Category ─────────────────────────────────────────────────────
class Category(Base):
    __tablename__ = "categories"
    id    = Column(Integer, primary_key=True)
    name  = Column(String, unique=True, nullable=False)
    slug  = Column(String, unique=True, nullable=False)

    posts = relationship("Post", back_populates="category")

# ── Tag ──────────────────────────────────────────────────────────
class Tag(Base):
    __tablename__ = "tags"
    id   = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    posts = relationship("Post", secondary=post_tags, back_populates="tags")

# ── Post ─────────────────────────────────────────────────────────
POST_TYPES = ("blog", "vlog")

class Post(Base):
    __tablename__ = "posts"
    id          = Column(Integer, primary_key=True)
    title       = Column(String, nullable=False)
    description = Column(String, nullable=False)
    type        = Column(String, default="blog")          # "blog" or "vlog"
    created_at  = Column(DateTime, default=datetime.utcnow)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    author_id   = Column(Integer, ForeignKey("users.id"),      nullable=False)

    category = relationship("Category", back_populates="posts")
    author   = relationship("User",     back_populates="posts")
    tags     = relationship("Tag", secondary=post_tags, back_populates="posts")