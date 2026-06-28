from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category
from ..schemas import (
    CategoryCreate, CategoryResponse,
    PricingRequest, PricingResponse
)
from ..utils.pricing import calculate_pricing
from ..dependencies import get_current_user, get_current_admin

router = APIRouter(tags=["定价"])


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).filter(Category.is_active == True).all()
    return categories


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin)
):
    existing = db.query(Category).filter(Category.code == category_data.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="品类编码已存在"
        )

    category = Category(**category_data.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.post("/pricing/calculate", response_model=PricingResponse)
def calculate_price(
    request: PricingRequest,
    db: Session = Depends(get_db),
    _=Depends(get_current_user)
):
    try:
        pricing_response, _ = calculate_pricing(db, request.items)
        return pricing_response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
