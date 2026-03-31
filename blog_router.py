from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

import models
from blog_schemas import BlogCreate, BlogResponse, BlogSummary, BlogDeleteResponse
from dependencies import get_db, get_current_user
from models import User, Blog

router = APIRouter(
    prefix="/blogs",
    tags=["Blogs"],
)


def resolve_categories(db: Session, ids: List[int]) -> List[models.Category]:
    categories = []
    for cat_id in ids:
        cat = db.query(models.Category).filter(models.Category.id == cat_id).first()
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category with id {cat_id} not found")
        categories.append(cat)
    return categories


def resolve_tags(db: Session, ids: List[int]) -> List[models.Tag]:
    tags = []
    for tag_id in ids:
        tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
        if not tag:
            raise HTTPException(status_code=404, detail=f"Tag with id {tag_id} not found")
        tags.append(tag)
    return tags

@router.post("/blogs/", response_model=BlogResponse)
def create_blog(
    blog: BlogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):

    new_blog = Blog(
        title=blog.title,
        description=blog.description,
        content=blog.content,
        user_id=current_user.id
    )

    db.add(new_blog)
    db.commit()
    db.refresh(new_blog)

    return {
        "id": new_blog.id,
        "title": new_blog.title,
        "description": new_blog.description,
        "content": new_blog.content,
        "owner_email": current_user.email
    }
@router.get("/", response_model=List[BlogSummary])
def get_all_blogs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),  # 👈 ADD THIS
    skip: int = 0,
    limit: int = 20,
    category_id: Optional[int] = None,
    tag_id: Optional[int] = None,
):
    if limit > 100:
        limit = 100

    query = db.query(models.Blog).filter(models.Blog.user_id == current_user.id)  # 👈 FILTER BY USER

    if category_id:
        query = query.filter(models.Blog.categories.any(models.Category.id == category_id))
    if tag_id:
        query = query.filter(models.Blog.tags.any(models.Tag.id == tag_id))

    return query.order_by(models.Blog.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{blog_id}", response_model=BlogResponse)
def get_blog_by_id(blog_id: int, db: Session = Depends(get_db)):
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail=f"Blog with id {blog_id} not found")
    return blog


@router.delete("/{blog_id}", response_model=BlogDeleteResponse)
def delete_blog(
    blog_id:      int,
    db:           Session     = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if not blog:
        raise HTTPException(status_code=404, detail=f"Blog with id {blog_id} not found")
    if blog.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not allowed to delete this blog post")

    db.delete(blog)
    db.commit()
    return BlogDeleteResponse(message="Blog deleted successfully", blog_id=blog_id)



@router.get("/my-blogs", response_model=List[BlogSummary])
def get_my_blogs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Blog)
        .filter(models.Blog.user_id == current_user.id)
        .order_by(models.Blog.created_at.desc())
        .all()
    )