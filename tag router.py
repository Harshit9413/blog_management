from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
from blog_schemas import TagCreate, TagResponse
from dependencies import get_db, get_admin_user


router = APIRouter(
    prefix="/tags",
    tags=["Tags"],
)


# ─────────────────────────────────────────────────────────────────────────────
#  1. CREATE  —  POST /tags/
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=TagResponse, status_code=201)
def create_tag(
    data:       TagCreate,
    db:         Session     = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    """
    Create a new tag.
    Only superadmin or clientadmin can create tags.
    Tag names are automatically lowercased.
    Returns 400 if the tag already exists.
    """
    existing = db.query(models.Tag).filter(
        models.Tag.name == data.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Tag '{data.name}' already exists",
        )

    tag = models.Tag(name=data.name)

    db.add(tag)
    db.commit()
    db.refresh(tag)

    return tag


# ─────────────────────────────────────────────────────────────────────────────
#  2. GET ALL  —  GET /tags/
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[TagResponse])
def get_all_tags(db: Session = Depends(get_db)):
    """
    Get all tags alphabetically.
    Public endpoint — no login required.
    """
    return db.query(models.Tag).order_by(models.Tag.name).all()


# ─────────────────────────────────────────────────────────────────────────────
#  3. GET ONE  —  GET /tags/{tag_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{tag_id}", response_model=TagResponse)
def get_tag_by_id(
    tag_id: int,
    db:     Session = Depends(get_db),
):
    """
    Get a single tag by ID.
    Public endpoint — no login required.
    Returns 404 if not found.
    """
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"Tag with id {tag_id} not found",
        )

    return tag


# ─────────────────────────────────────────────────────────────────────────────
#  4. UPDATE  —  PUT /tags/{tag_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id:     int,
    data:       TagCreate,
    db:         Session     = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    """
    Update a tag's name.
    Only superadmin or clientadmin can update.
    Returns 404 if not found, 400 if new name is already taken.
    """
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"Tag with id {tag_id} not found",
        )

    dup = db.query(models.Tag).filter(
        models.Tag.name == data.name,
        models.Tag.id   != tag_id,
    ).first()

    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"Tag name '{data.name}' is already taken",
        )

    tag.name = data.name

    db.commit()
    db.refresh(tag)

    return tag


# ─────────────────────────────────────────────────────────────────────────────
#  5. DELETE  —  DELETE /tags/{tag_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{tag_id}")
def delete_tag(
    tag_id:     int,
    db:         Session     = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    """
    Delete a tag by ID.
    Only superadmin or clientadmin can delete.
    Blogs linked to this tag simply lose the association.
    Returns 404 if not found.
    """
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()

    if not tag:
        raise HTTPException(
            status_code=404,
            detail=f"Tag with id {tag_id} not found",
        )

    db.delete(tag)
    db.commit()

    return {"message": "Tag deleted successfully", "tag_id": tag_id}