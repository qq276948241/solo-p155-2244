from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import User, Order, Rating
from ..schemas import RatingCreate, RatingResponse, CollectorRatingSummary
from ..dependencies import get_current_resident, get_current_user

router = APIRouter(prefix="/orders", tags=["评价"])


@router.post("/{order_id}/rate", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
def rate_order(
    order_id: int,
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_resident),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    if order.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能评价已完成的订单"
        )

    if not order.collector_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该订单无回收员，无法评价"
        )

    existing = db.query(Rating).filter(Rating.order_id == order_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该订单已评价，不可重复提交"
        )

    rating = Rating(
        order_id=order_id,
        user_id=current_user.id,
        collector_id=order.collector_id,
        score=rating_data.score,
        comment=rating_data.comment
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)

    return RatingResponse(
        id=rating.id,
        order_id=rating.order_id,
        user_id=rating.user_id,
        collector_id=rating.collector_id,
        score=rating.score,
        comment=rating.comment,
        user_name=current_user.name,
        created_at=rating.created_at
    )


@router.get("/{order_id}/rate", response_model=RatingResponse)
def get_order_rating(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    rating = db.query(Rating).filter(Rating.order_id == order_id).first()
    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="该订单暂无评价"
        )

    user = db.query(User).filter(User.id == rating.user_id).first()

    return RatingResponse(
        id=rating.id,
        order_id=rating.order_id,
        user_id=rating.user_id,
        collector_id=rating.collector_id,
        score=rating.score,
        comment=rating.comment,
        user_name=user.name if user else None,
        created_at=rating.created_at
    )


@router.get("/collector/{collector_id}/ratings", response_model=CollectorRatingSummary)
def get_collector_ratings(
    collector_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    collector = db.query(User).filter(
        User.id == collector_id,
        User.role.in_(["collector", "admin"])
    ).first()
    if not collector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="回收员不存在"
        )

    ratings = db.query(Rating).filter(
        Rating.collector_id == collector_id
    ).order_by(Rating.created_at.desc()).all()

    avg_result = db.query(func.avg(Rating.score)).filter(
        Rating.collector_id == collector_id
    ).scalar()
    avg_score = round(float(avg_result), 1) if avg_result else 0.0

    rating_responses = []
    for r in ratings:
        user = db.query(User).filter(User.id == r.user_id).first()
        rating_responses.append(RatingResponse(
            id=r.id,
            order_id=r.order_id,
            user_id=r.user_id,
            collector_id=r.collector_id,
            score=r.score,
            comment=r.comment,
            user_name=user.name if user else None,
            created_at=r.created_at
        ))

    return CollectorRatingSummary(
        collector_id=collector_id,
        collector_name=collector.name,
        average_score=avg_score,
        total_count=len(ratings),
        ratings=rating_responses
    )
