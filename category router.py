from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
from blog_schemas import CategoryCreate, CategoryResponse
from dependencies import get_db, get_admin_user


router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)


# ─────────────────────────────────────────────────────────────────────────────
#  1. CREATE  —  POST /categories/
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=CategoryResponse, status_code=201)
def create_category(
    data:       CategoryCreate,
    db:         Session     = Depends(get_db),
    admin_user: models.User = Depends(get_admin_user),
):
    """
    Create a new category.
    Only superadmin or clientadmin can create categories.
    Returns 400 if a category with the same name already exists.
    """
    existing = db.query(models.Category).filter(
        models.Category.name == data.name
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{data.name}' already exists",
        )

    category = models.Category(
        name        = data.name,
        description = data.description,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


# ─────────────────────────────────────────────────────────────────────────────
#  2. GET ALL  —  GET /categories/
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CategoryResponse])
def get_all_categories(db: Session = Depends(get_db)):
    """
    Get all categories alphabetically.
    Public endpoint — no login required.
    """
    return db.query(models.Category).order_by(models.Category.name).all()


# ─────────────────────────────────────────────────────────────────────────────
#  3. GET ONE  —  GET /categories/{category_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{category_id}", response_model=CategoryResponse)
def get_category_by_id(
    category_id: int,
    db:          Session = Depends(get_db),
):
    """
    Get a single category by ID.
    Public endpoint — no login required.
    Returns 404 if not found.
    """
    category = db.query(models.Category).filter(
        models.Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail=f"Category with id {category_id} not found",
        )

    return category


# ─────────────────────────────────────────────────────────────────────────────
#  4. UPDATE  —  PUT /categories/{category_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data:        CategoryCreate,
    db:          Session     = Depends(get_db),
    admin_user:  models.User = Depends(get_admin_user),
):
    """
    Update a category's name and/or description.
    Only superadmin or clientadmin can update.
    Returns 404 if not found, 400 if new name is already taken.
    """
    category = db.query(models.Category).filter(
        models.Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail=f"Category with id {category_id} not found",
        )

    dup = db.query(models.Category).filter(
        models.Category.name == data.name,
        models.Category.id   != category_id,
    ).first()

    if dup:
        raise HTTPException(
            status_code=400,
            detail=f"Category name '{data.name}' is already taken",
        )

    category.name        = data.name
    category.description = data.description

    db.commit()
    db.refresh(category)

    return category


# ─────────────────────────────────────────────────────────────────────────────
#  5. DELETE  —  DELETE /categories/{category_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{category_id}")
def delete_category(
    category_id: int,
    db:          Session     = Depends(get_db),
    admin_user:  models.User = Depends(get_admin_user),
):
    """
    Delete a category by ID.
    Only superadmin or clientadmin can delete.
    Blogs linked to this category simply lose the association.
    Returns 404 if not found.
    """
    category = db.query(models.Category).filter(
        models.Category.id == category_id
    ).first()

    if not category:
        raise HTTPException(
            status_code=404,
            detail=f"Category with id {category_id} not found",
        )

    db.delete(category)
    db.commit()

    return {"message": "Category deleted successfully", "category_id": category_id}