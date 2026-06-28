from typing import List, Tuple
from sqlalchemy.orm import Session

from ..models import Category
from ..schemas import PricingItem, PricingDetail, PricingResponse


def calculate_pricing(db: Session, items: List[PricingItem]) -> Tuple[PricingResponse, List[dict]]:
    details = []
    order_items = []
    total_amount = 0.0
    total_weight = 0.0

    category_map = {cat.code: cat for cat in db.query(Category).filter(Category.is_active == True).all()}

    for item in items:
        category = category_map.get(item.category_code)
        if not category:
            raise ValueError(f"品类 {item.category_code} 不存在或已停用")

        subtotal = round(category.unit_price * item.estimated_weight, 2)
        total_amount += subtotal
        total_weight += item.estimated_weight

        details.append(PricingDetail(
            category_code=category.code,
            category_name=category.name,
            unit_price=category.unit_price,
            estimated_weight=item.estimated_weight,
            subtotal=subtotal
        ))

        order_items.append({
            "category_id": category.id,
            "category_code": category.code,
            "category_name": category.name,
            "estimated_weight": item.estimated_weight,
            "unit_price": category.unit_price,
            "subtotal": subtotal
        })

    total_amount = round(total_amount, 2)
    total_weight = round(total_weight, 2)

    return PricingResponse(
        details=details,
        total_amount=total_amount,
        total_weight=total_weight
    ), order_items
