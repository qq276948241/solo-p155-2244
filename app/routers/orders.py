from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import User, Order, OrderItem, Address, Category, Rating
from ..schemas import (
    OrderCreate, OrderResponse, OrderUpdateTime, OrderComplete,
    PricingItem, RatingCreate, RatingResponse, CollectorRatingSummary
)
from ..utils.pricing import calculate_pricing
from ..dependencies import get_current_resident, get_current_user, get_current_collector

router = APIRouter(prefix="/orders", tags=["订单"])


def generate_order_no():
    return f"RC{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{datetime.utcnow().microsecond // 1000:03d}"


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_data: OrderCreate,
    current_user: User = Depends(get_current_resident),
    db: Session = Depends(get_db)
):
    address = db.query(Address).filter(
        Address.id == order_data.address_id,
        Address.user_id == current_user.id
    ).first()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="地址不存在"
        )

    pricing_items = []
    for item in order_data.items:
        category = db.query(Category).filter(
            Category.id == item.category_id,
            Category.is_active == True
        ).first()
        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"品类ID {item.category_id} 不存在或已停用"
            )
        pricing_items.append(PricingItem(
            category_code=category.code,
            estimated_weight=item.estimated_weight
        ))

    try:
        pricing_result, order_items_data = calculate_pricing(db, pricing_items)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    order = Order(
        order_no=generate_order_no(),
        user_id=current_user.id,
        address_id=order_data.address_id,
        scheduled_date=order_data.scheduled_date,
        scheduled_time_slot=order_data.scheduled_time_slot,
        remark=order_data.remark,
        total_amount=pricing_result.total_amount,
        status="pending"
    )
    db.add(order)
    db.flush()

    for item_data in order_items_data:
        order_item = OrderItem(
            order_id=order.id,
            category_id=item_data["category_id"],
            estimated_weight=item_data["estimated_weight"],
            unit_price=item_data["unit_price"],
            subtotal=item_data["subtotal"]
        )
        db.add(order_item)

    db.commit()
    db.refresh(order)

    response_items = []
    for item in order.items:
        category = db.query(Category).filter(Category.id == item.category_id).first()
        response_items.append({
            "id": item.id,
            "category_id": item.category_id,
            "category_name": category.name if category else None,
            "category_code": category.code if category else None,
            "estimated_weight": item.estimated_weight,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
            "actual_weight": item.actual_weight,
            "created_at": item.created_at
        })

    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        collector_id=order.collector_id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        scheduled_time_slot=order.scheduled_time_slot,
        address_id=order.address_id,
        remark=order.remark,
        actual_weight=order.actual_weight,
        total_amount=order.total_amount,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=response_items,
        address=order.address
    )


@router.get("", response_model=List[OrderResponse])
def get_my_orders(
    status: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Order).filter(Order.user_id == current_user.id)
    if status:
        query = query.filter(Order.status == status)
    orders = query.order_by(Order.created_at.desc()).all()

    response_orders = []
    for order in orders:
        response_items = []
        for item in order.items:
            category = db.query(Category).filter(Category.id == item.category_id).first()
            response_items.append({
                "id": item.id,
                "category_id": item.category_id,
                "category_name": category.name if category else None,
                "category_code": category.code if category else None,
                "estimated_weight": item.estimated_weight,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal,
                "actual_weight": item.actual_weight,
                "created_at": item.created_at
            })
        response_orders.append(OrderResponse(
            id=order.id,
            order_no=order.order_no,
            user_id=order.user_id,
            collector_id=order.collector_id,
            status=order.status,
            scheduled_date=order.scheduled_date,
            scheduled_time_slot=order.scheduled_time_slot,
            address_id=order.address_id,
            remark=order.remark,
            actual_weight=order.actual_weight,
            total_amount=order.total_amount,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=response_items,
            address=order.address
        ))
    return response_orders


@router.get("/{order_id}", response_model=OrderResponse)
def get_order_detail(
    order_id: int,
    current_user: User = Depends(get_current_user),
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

    response_items = []
    for item in order.items:
        category = db.query(Category).filter(Category.id == item.category_id).first()
        response_items.append({
            "id": item.id,
            "category_id": item.category_id,
            "category_name": category.name if category else None,
            "category_code": category.code if category else None,
            "estimated_weight": item.estimated_weight,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
            "actual_weight": item.actual_weight,
            "created_at": item.created_at
        })

    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        collector_id=order.collector_id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        scheduled_time_slot=order.scheduled_time_slot,
        address_id=order.address_id,
        remark=order.remark,
        actual_weight=order.actual_weight,
        total_amount=order.total_amount,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=response_items,
        address=order.address
    )


@router.put("/{order_id}/reschedule", response_model=OrderResponse)
def reschedule_order(
    order_id: int,
    time_data: OrderUpdateTime,
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

    if order.status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已完成或已取消的订单无法改期"
        )

    order.scheduled_date = time_data.scheduled_date
    order.scheduled_time_slot = time_data.scheduled_time_slot
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    response_items = []
    for item in order.items:
        category = db.query(Category).filter(Category.id == item.category_id).first()
        response_items.append({
            "id": item.id,
            "category_id": item.category_id,
            "category_name": category.name if category else None,
            "category_code": category.code if category else None,
            "estimated_weight": item.estimated_weight,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
            "actual_weight": item.actual_weight,
            "created_at": item.created_at
        })

    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        collector_id=order.collector_id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        scheduled_time_slot=order.scheduled_time_slot,
        address_id=order.address_id,
        remark=order.remark,
        actual_weight=order.actual_weight,
        total_amount=order.total_amount,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=response_items,
        address=order.address
    )


@router.put("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
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

    if order.status in ["completed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订单已完成或已取消"
        )

    order.status = "cancelled"
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    response_items = []
    for item in order.items:
        category = db.query(Category).filter(Category.id == item.category_id).first()
        response_items.append({
            "id": item.id,
            "category_id": item.category_id,
            "category_name": category.name if category else None,
            "category_code": category.code if category else None,
            "estimated_weight": item.estimated_weight,
            "unit_price": item.unit_price,
            "subtotal": item.subtotal,
            "actual_weight": item.actual_weight,
            "created_at": item.created_at
        })

    return OrderResponse(
        id=order.id,
        order_no=order.order_no,
        user_id=order.user_id,
        collector_id=order.collector_id,
        status=order.status,
        scheduled_date=order.scheduled_date,
        scheduled_time_slot=order.scheduled_time_slot,
        address_id=order.address_id,
        remark=order.remark,
        actual_weight=order.actual_weight,
        total_amount=order.total_amount,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=response_items,
        address=order.address
    )


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
