from typing import List
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Order, OrderItem, Category
from ..schemas import (
    CollectorOrderResponse, CollectorOrderItem,
    OrderComplete, RoutePoint
)
from ..dependencies import get_current_collector

router = APIRouter(prefix="/collector", tags=["回收员"])


@router.get("/orders/today", response_model=List[CollectorOrderResponse])
def get_today_orders(
    current_user: User = Depends(get_current_collector),
    db: Session = Depends(get_db)
):
    today = date.today()
    orders = db.query(Order).filter(
        Order.scheduled_date == today,
        Order.status.in_(["pending", "assigned", "in_progress"])
    ).order_by(Order.scheduled_time_slot, Order.created_at).all()

    return _build_collector_orders(orders, db)


@router.get("/orders", response_model=List[CollectorOrderResponse])
def get_my_orders(
    status: str = None,
    current_user: User = Depends(get_current_collector),
    db: Session = Depends(get_db)
):
    query = db.query(Order).filter(Order.collector_id == current_user.id)
    if status:
        query = query.filter(Order.status == status)
    orders = query.order_by(Order.created_at.desc()).all()

    return _build_collector_orders(orders, db)


@router.put("/orders/{order_id}/accept", response_model=CollectorOrderResponse)
def accept_order(
    order_id: int,
    current_user: User = Depends(get_current_collector),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    if order.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订单状态不允许接单"
        )

    order.collector_id = current_user.id
    order.status = "assigned"
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return _build_collector_orders([order], db)[0]


@router.put("/orders/{order_id}/start", response_model=CollectorOrderResponse)
def start_order(
    order_id: int,
    current_user: User = Depends(get_current_collector),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.collector_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    if order.status != "assigned":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订单状态不允许开始"
        )

    order.status = "in_progress"
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return _build_collector_orders([order], db)[0]


@router.put("/orders/{order_id}/complete", response_model=CollectorOrderResponse)
def complete_order(
    order_id: int,
    complete_data: OrderComplete,
    current_user: User = Depends(get_current_collector),
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.collector_id == current_user.id
    ).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="订单不存在"
        )

    if order.status not in ["assigned", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="订单状态不允许完成"
        )

    order.status = "completed"
    if complete_data.actual_weight is not None:
        order.actual_weight = complete_data.actual_weight
    if complete_data.total_amount is not None:
        order.total_amount = complete_data.total_amount
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return _build_collector_orders([order], db)[0]


@router.get("/route/today", response_model=List[RoutePoint])
def get_today_route(
    current_user: User = Depends(get_current_collector),
    db: Session = Depends(get_db)
):
    today = date.today()
    orders = db.query(Order).filter(
        Order.scheduled_date == today,
        Order.collector_id == current_user.id,
        Order.status.in_(["assigned", "in_progress"])
    ).order_by(Order.scheduled_time_slot, Order.created_at).all()

    route_points = []
    for idx, order in enumerate(orders):
        address = order.address
        full_address = f"{address.province}{address.city}{address.district}{address.detail}"
        total_weight = sum(item.estimated_weight for item in order.items)

        route_points.append(RoutePoint(
            order_id=order.id,
            order_no=order.order_no,
            address=full_address,
            contact_name=address.contact_name,
            contact_phone=address.contact_phone,
            sequence=idx + 1,
            estimated_weight=round(total_weight, 2)
        ))

    return route_points


def _build_collector_orders(orders, db):
    result = []
    for order in orders:
        address = order.address
        user = order.user
        full_address = f"{address.province}{address.city}{address.district}{address.detail}"

        items = []
        total_weight = 0.0
        for item in order.items:
            category = db.query(Category).filter(Category.id == item.category_id).first()
            items.append(CollectorOrderItem(
                id=item.id,
                category_name=category.name if category else "未知",
                estimated_weight=item.estimated_weight,
                actual_weight=item.actual_weight,
                unit_price=item.unit_price,
                subtotal=item.subtotal
            ))
            total_weight += item.estimated_weight

        result.append(CollectorOrderResponse(
            id=order.id,
            order_no=order.order_no,
            status=order.status,
            scheduled_date=order.scheduled_date,
            scheduled_time_slot=order.scheduled_time_slot,
            user_name=user.name,
            user_phone=user.phone,
            address=full_address,
            total_estimated_weight=round(total_weight, 2),
            total_amount=order.total_amount,
            actual_weight=order.actual_weight,
            items=items,
            remark=order.remark
        ))
    return result
