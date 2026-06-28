from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None


class UserBase(BaseModel):
    phone: str
    name: str


class UserCreate(UserBase):
    password: str
    role: str = "resident"

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ["resident", "collector", "admin"]:
            raise ValueError("角色必须是 resident、collector 或 admin")
        return v


class UserLogin(BaseModel):
    phone: str
    password: str


class UserResponse(UserBase):
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class AddressBase(BaseModel):
    province: str
    city: str
    district: str
    detail: str
    contact_name: str
    contact_phone: str
    is_default: bool = False


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    province: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    detail: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    is_default: Optional[bool] = None


class AddressResponse(AddressBase):
    id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryBase(BaseModel):
    name: str
    code: str
    unit_price: float
    description: Optional[str] = None


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PricingItem(BaseModel):
    category_code: str
    estimated_weight: float = Field(gt=0, description="预估重量，单位：公斤")


class PricingRequest(BaseModel):
    items: List[PricingItem]


class PricingDetail(BaseModel):
    category_code: str
    category_name: str
    unit_price: float
    estimated_weight: float
    subtotal: float


class PricingResponse(BaseModel):
    details: List[PricingDetail]
    total_amount: float
    total_weight: float


class OrderItemBase(BaseModel):
    category_id: int
    estimated_weight: float


class OrderItemCreate(OrderItemBase):
    pass


class OrderItemResponse(OrderItemBase):
    id: int
    category_name: Optional[str] = None
    category_code: Optional[str] = None
    unit_price: float
    subtotal: float
    actual_weight: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrderBase(BaseModel):
    scheduled_date: date
    scheduled_time_slot: str
    address_id: int
    remark: Optional[str] = None

    @field_validator("scheduled_time_slot")
    @classmethod
    def validate_time_slot(cls, v):
        if v not in ["morning", "afternoon", "all_day"]:
            raise ValueError("时间段必须是 morning、afternoon 或 all_day")
        return v


class OrderCreate(OrderBase):
    items: List[OrderItemCreate]


class OrderUpdateTime(BaseModel):
    scheduled_date: date
    scheduled_time_slot: str

    @field_validator("scheduled_time_slot")
    @classmethod
    def validate_time_slot(cls, v):
        if v not in ["morning", "afternoon", "all_day"]:
            raise ValueError("时间段必须是 morning、afternoon 或 all_day")
        return v


class OrderComplete(BaseModel):
    actual_weight: Optional[float] = None
    total_amount: Optional[float] = None


class OrderResponse(OrderBase):
    id: int
    order_no: str
    user_id: int
    collector_id: Optional[int] = None
    status: str
    actual_weight: Optional[float] = None
    total_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
    address: Optional[AddressResponse] = None

    class Config:
        from_attributes = True


class CollectorOrderItem(BaseModel):
    id: int
    category_name: str
    estimated_weight: float
    actual_weight: Optional[float] = None
    unit_price: float
    subtotal: float


class CollectorOrderResponse(BaseModel):
    id: int
    order_no: str
    status: str
    scheduled_date: date
    scheduled_time_slot: str
    user_name: str
    user_phone: str
    address: str
    total_estimated_weight: float
    total_amount: Optional[float] = None
    actual_weight: Optional[float] = None
    items: List[CollectorOrderItem]
    remark: Optional[str] = None

    class Config:
        from_attributes = True


class RoutePoint(BaseModel):
    order_id: int
    order_no: str
    address: str
    contact_name: str
    contact_phone: str
    sequence: int
    estimated_weight: float


class RatingCreate(BaseModel):
    score: int = Field(ge=1, le=5, description="评分，1到5星")
    comment: Optional[str] = Field(None, max_length=200, description="评语，不超过200字")


class RatingResponse(BaseModel):
    id: int
    order_id: int
    user_id: int
    collector_id: int
    score: int
    comment: Optional[str] = None
    user_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CollectorRatingSummary(BaseModel):
    collector_id: int
    collector_name: str
    average_score: float
    total_count: int
    ratings: List[RatingResponse]
