from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

import models
from blog_schemas import BlogCreate, BlogResponse, BlogSummary, BlogDeleteResponse
from dependencies import get_db, get_current_user


router = APIRouter(
    prefix="/blogs",
    tags=["Blogs"],
)


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS — resolve IDs to model instances
# ─────────────────────────────────────────────────────────────────────────────

def resolve_categories(db: Session, ids: List[int]) -> List[models.Category]:
    """Fetch Category objects for the given IDs. Raises 404 if any is missing."""
    categories = []
    for cat_id in ids:
        cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
        if not cat:
            raise HTTPException(
                status_code=404,
                detail=f"Category with id {cat_id} not found",
            )
        categories.append(cat)
    return categories


def resolve_tags(db: Session, ids: List[int]) -> List[models.Tag]:
    """Fetch Tag objects for the given IDs. Raises 404 if any is missing."""
    tags = []
    for tag_id in ids:
        tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
        if not tag:
            raise HTTPException(
                status_code=404,
                detail=f"Tag with id {tag_id} not found",
            )
        tags.append(tag)
    return tags


# ─────────────────────────────────────────────────────────────────────────────
#  1.  CREATE BLOG  —  POST /blogs/
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=BlogResponse, status_code=201)
def create_blog(
    blog_data:    BlogCreate,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create a new blog post.
    Requires login. Blog is automatically linked to the logged-in user.
    Optionally pass category_ids and tag_ids to link existing categories/tags.

    Request body example:
    {
        "title": "My Post",
        "description": "Short intro",
        "content": "Full content...",
        "category_ids": [1, 2],
        "tag_ids": [3, 5]
    }
    """
    categories = resolve_categories(db, blog_data.category_ids or [])
    tags       = resolve_tags(db,       blog_data.tag_ids      or [])

    new_blog = models.Blog(
        title       = blog_data.title,
        description = blog_data.description,
        content     = blog_data.content,
        user_id     = current_user.id,
        categories  = categories,
        tags        = tags,
    )

    db.add(new_blog)
    db.commit()
    db.refresh(new_blog)

    return new_blog


# ─────────────────────────────────────────────────────────────────────────────
#  2.  GET ALL BLOGS  —  GET /blogs/
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[BlogSummary])
def get_all_blogs(
    db:          Session       = Depends(get_db),
    skip:        int           = 0,
    limit:       int           = 20,
    category_id: Optional[int] = None,
    tag_id:      Optional[int] = None,
):
    """
    Get all blog posts, newest first.
    Public endpoint — no login required.

    Query params:
      ?skip=0          — pagination offset (default 0)
      ?limit=20        — max results (default 20, hard cap 100)
      ?category_id=1   — filter blogs by a specific category
      ?tag_id=2        — filter blogs by a specific tag
    """
    if limit > 100:
        limit = 100

    query = db.query(models.Blog)

    if category_id:
        query = query.filter(
            models.Blog.categories.any(models.Category.id == category_id)
        )

    if tag_id:
        query = query.filter(
            models.Blog.tags.any(models.Tag.id == tag_id)
        )

    return (
        query
        .order_by(models.Blog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ─────────────────────────────────────────────────────────────────────────────
#  3.  GET SINGLE BLOG  —  GET /blogs/{blog_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{blog_id}", response_model=BlogResponse)
def get_blog_by_id(
    blog_id: int,
    db:      Session = Depends(get_db),
):
    """
    Get a single blog post by ID including full content, categories and tags.
    Public endpoint — no login required.
    Returns 404 if the blog does not exist.
    """
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()

    if not blog:
        raise HTTPException(
            status_code=404,
            detail=f"Blog with id {blog_id} not found",
        )

    return blog


# ─────────────────────────────────────────────────────────────────────────────
#  4.  DELETE BLOG  —  DELETE /blogs/{blog_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{blog_id}", response_model=BlogDeleteResponse)
def delete_blog(
    blog_id:      int,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Delete a blog post by ID.
    Requires login. Only the owner of the blog can delete it.
    Returns 404 if not found, 403 if not the owner.
    """
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()

    if not blog:
        raise HTTPException(
            status_code=404,
            detail=f"Blog with id {blog_id} not found",
        )

    if blog.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You are not allowed to delete this blog post",
        )

    db.delete(blog)
    db.commit()

    return BlogDeleteResponse(
        message = "Blog deleted successfully",
        blog_id = blog_id,
    )