"""
models.py
---------
SQLAlchemy ORM models: users, foods, tables, reservations, orders, order_items.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    orders = relationship("Order", back_populates="user")
    reservations = relationship("Reservation", back_populates="user")


class Food(Base):
    __tablename__ = "foods"

    food_id = Column(Integer, primary_key=True, index=True)
    food_name = Column(String(120), nullable=False)
    category = Column(String(60), nullable=False)       # e.g. Starters, Main Course, Beverages
    price = Column(Float, nullable=False)
    description = Column(Text, default="")
    is_veg = Column(Boolean, default=True)
    spice_level = Column(Integer, default=1)             # 1-3 (mild/medium/spicy)
    image_url = Column(String(255), default="")
    availability = Column(Boolean, default=True)
    rating = Column(Float, default=4.5)

    order_items = relationship("OrderItem", back_populates="food")


class RestaurantTable(Base):
    __tablename__ = "tables"

    table_id = Column(Integer, primary_key=True, index=True)
    table_number = Column(String(10), unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    status = Column(String(20), default="available")     # available / reserved / occupied

    reservations = relationship("Reservation", back_populates="table")


class Reservation(Base):
    __tablename__ = "reservations"

    reservation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    customer_name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(120), default="")
    reservation_date = Column(String(20), nullable=False)   # YYYY-MM-DD
    reservation_time = Column(String(10), nullable=False)   # HH:MM
    guests = Column(Integer, nullable=False)
    special_request = Column(Text, default="")
    table_id = Column(Integer, ForeignKey("tables.table_id"), nullable=True)
    status = Column(String(20), default="confirmed")        # confirmed / cancelled
    admin_note = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    table = relationship("RestaurantTable", back_populates="reservations")
    user = relationship("User", back_populates="reservations")


class Order(Base):
    __tablename__ = "orders"

    order_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    customer_name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(120), default="")
    address = Column(String(255), default="")
    landmark = Column(String(255), default="")
    delivery_instructions = Column(Text, default="")
    payment_method = Column(String(30), default="cod")      # cod / upi (simulated)
    total_amount = Column(Float, nullable=False)
    order_date = Column(DateTime(timezone=True), server_default=func.now())
    # Order Placed -> Confirmed -> Preparing -> Out for Delivery -> Delivered
    # (also: Cancelled, Change Requested)
    status = Column(String(30), default="Order Placed")
    admin_note = Column(Text, default="")

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    user = relationship("User", back_populates="orders")


class OrderItem(Base):
    __tablename__ = "order_items"

    order_item_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.food_id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)   # price at time of order

    order = relationship("Order", back_populates="items")
    food = relationship("Food", back_populates="order_items")
