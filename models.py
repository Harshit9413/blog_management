from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Table, event
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

blog_categories = Table(
    "blog_categories", Base.metadata,
    Column("blog_id",     Integer, ForeignKey("blogs.id",      ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)

blog_tags = Table(
    "blog_tags", Base.metadata,
    Column("blog_id", Integer, ForeignKey("blogs.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id",  Integer, ForeignKey("tags.id",  ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True)
    email      = Column(String, unique=True, nullable=False)
    password   = Column(String, nullable=False)
    gender     = Column(String, nullable=True)
    phone      = Column(String, nullable=True)
    otp        = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    role       = Column(String, default="user")
    is_active  = Column(Boolean, default=True)

    blogs = relationship("Blog", back_populates="owner", cascade="all, delete-orphan")


# 🔒 Prevent superadmin role from being changed via ORM
@event.listens_for(User, "before_update")
def lock_superadmin_role(mapper, connection, target):
    from sqlalchemy import inspect
    state = inspect(target)
    role_history = state.attrs.role.history
    if role_history.deleted and "superadmin" in role_history.deleted:
        raise ValueError("Superadmin role cannot be changed!")


class Category(Base):
    __tablename__ = "categories"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), unique=True, nullable=False)
    description = Column(String(300), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    blogs = relationship("Blog", secondary=blog_categories, back_populates="categories")


class Tag(Base):
    __tablename__ = "tags"

    id         = Column(Integer, primary_key=True, index=True)
    name       = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    blogs = relationship("Blog", secondary=blog_tags, back_populates="tags")


class Blog(Base):
    __tablename__ = "blogs"

    id          = Column(Integer, primary_key=True, index=True)
    title       = Column(String(255), nullable=False)
    description = Column(String(500), nullable=False)
    content     = Column(Text, nullable=False)
     
    user_id     = Column(Integer, ForeignKey("users.id"))
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner      = relationship("User", back_populates="blogs")
    categories = relationship("Category", secondary=blog_categories, back_populates="blogs")
    tags       = relationship("Tag",      secondary=blog_tags,       back_populates="blogs")

    @property
    def owner_email(self):
        return self.owner.email 