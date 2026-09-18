"""
schemas.py
----------
Pydantic models used for request bodies and API responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ---------- Auth ----------

class RegisterRequest(BaseModel):
    name: str
    email: str
    phone: str
    password: str


class LoginRequest(BaseModel):
    identifier: str   # email or phone
    password: str


class UserOut(BaseModel):
    user_id: int
    name: str
    email: str
    phone: str
    is_admin: bool

    class Config:
        from_attributes = True


# ---------- Foods ----------

class FoodOut(BaseModel):
    food_id: int
    food_name: str
    category: str
    price: float
    description: str
    is_veg: bool
    spice_level: int
    image_url: str
    availability: bool
    rating: float

    class Config:
        from_attributes = True


# ---------- Table availability / reservations ----------

class AvailabilityQuery(BaseModel):
    date: str
    time: str
    guests: int


class ReservationCreate(BaseModel):
    customer_name: str
    phone: str
    email: Optional[str] = ""
    reservation_date: str
    reservation_time: str
    guests: int
    special_request: Optional[str] = ""
    table_id: Optional[int] = None


class ReservationOut(BaseModel):
    reservation_id: int
    customer_name: str
    phone: str
    email: str
    reservation_date: str
    reservation_time: str
    guests: int
    special_request: str
    table_id: Optional[int]
    status: str

    class Config:
        from_attributes = True


# ---------- Orders ----------

class OrderItemIn(BaseModel):
    food_id: int
    quantity: int


class OrderCreate(BaseModel):
    customer_name: str
    phone: str
    email: Optional[str] = ""
    address: str
    landmark: Optional[str] = ""
    delivery_instructions: Optional[str] = ""
    payment_method: str = "cod"
    items: List[OrderItemIn]


class OrderItemOut(BaseModel):
    food_id: int
    food_name: str
    quantity: int
    price: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    order_id: int
    customer_name: str
    phone: str
    address: str
    total_amount: float
    status: str
    items: List[OrderItemOut]

    class Config:
        from_attributes = True


# ---------- AI Assistant ----------

class AIRecommendRequest(BaseModel):
    message: str


class AIRecommendedDish(BaseModel):
    food_id: int
    food_name: str
    price: float
    reason: str


class AIRecommendResponse(BaseModel):
    reply: str
    recommendations: List[AIRecommendedDish]
    off_topic: bool = False
