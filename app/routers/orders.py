from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Order, OrderItem, Address, Category
from ..schemas import (
    OrderCreate, OrderResponse, OrderUpdateTime, OrderComplete,
    PricingItem
)
from ..utils.pricing import calculate_pricing
from ..dependencies import get_current_resident, get_current_user

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
