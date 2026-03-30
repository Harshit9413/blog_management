from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
#  CATEGORY SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name:        str
    description: Optional[str] = None

    @field_validator("name")
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Category name cannot be empty")
        if len(v) > 100:
            raise ValueError("Category name must be under 100 characters")
        return v

    @field_validator("description")
    def validate_description(cls, v):
        if v and len(v.strip()) > 300:
            raise ValueError("Description must be under 300 characters")
        return v.strip() if v else v


class CategoryResponse(BaseModel):
    id:          int
    name:        str
    description: Optional[str]
    created_at:  datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
#  TAG SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class TagCreate(BaseModel):
    name: str

    @field_validator("name")
    def validate_name(cls, v):
        v = v.strip().lower()
        if not v:
            raise ValueError("Tag name cannot be empty")
        if len(v) > 50:
            raise ValueError("Tag name must be under 50 characters")
        return v


class TagResponse(BaseModel):
    id:         int
    name:       str
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────────────────────────────────────────────────────────
#  BLOG SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class BlogCreate(BaseModel):
    title:        str
    description:  str
    content:      str
    category_ids: Optional[List[int]] = []
    tag_ids:      Optional[List[int]] = []

    @field_validator("title")
    def validate_title(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 255:
            raise ValueError("Title must be under 255 characters")
        return v

    @field_validator("description")
    def validate_description(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty")
        if len(v) > 500:
            raise ValueError("Description must be under 500 characters")
        return v

    @field_validator("content")
    def validate_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Content cannot be empty")
        return v


class BlogOwner(BaseModel):
    id:    int
    email: str

    class Config:
        from_attributes = True


class BlogResponse(BaseModel):
    """Full blog — used for create and get-by-id."""
    id:          int
    title:       str
    description: str
    content:     str
    user_id:     int
    created_at:  datetime
    updated_at:  datetime
    owner:       BlogOwner
    categories:  List[CategoryResponse] = []
    tags:        List[TagResponse]      = []

    class Config:
        from_attributes = True


class BlogSummary(BaseModel):
    """Lightweight — used in list endpoint, no content field."""
    id:          int
    title:       str
    description: str
    user_id:     int
    created_at:  datetime
    owner:       BlogOwner
    categories:  List[CategoryResponse] = []
    tags:        List[TagResponse]      = []

    class Config:
        from_attributes = True


class BlogDeleteResponse(BaseModel):
    message: str
    blog_id: int