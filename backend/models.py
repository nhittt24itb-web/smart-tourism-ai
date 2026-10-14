from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    SmallInteger,
    String,
    Boolean,
    Float,
    Text,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base
from datetime import datetime

# Bảng phân quyền Role
class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_name = Column(String(50), primary_key=True, default="user")

# Bảng Người dùng
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone_number = Column(String(20), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Bảng Điểm đến du lịch (Khớp 100% cột trong destinations.sql)
class Destination(Base):
    __tablename__ = "destinations"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    category_id = Column(BigInteger, nullable=False)
    name = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    short_description = Column(String(500), nullable=True)
    city = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=True)
    address = Column(String(300), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    price_level = Column(String(20), default="Medium")
    estimated_cost = Column(Float, default=0)
    opening_time = Column(String(20), default="08:00")
    closing_time = Column(String(20), default="22:00")
    average_visit_duration = Column(Integer, default=120)
    rating = Column(Float, default=0, index=True)
    review_count = Column(Integer, default=0)
    is_indoor = Column(Boolean, default=False)
    is_outdoor = Column(Boolean, default=True)
    family_friendly = Column(Boolean, default=True)
    kid_friendly = Column(Boolean, default=True)
    elderly_friendly = Column(Boolean, default=True)
    romantic_score = Column(Float, default=0.5)
    adventure_score = Column(Float, default=0.5)
    relaxation_score = Column(Float, default=0.5)
    photography_score = Column(Float, default=0.5)
    food_score = Column(Float, default=0.5)
    rain_suitability = Column(Float, default=0.5)
    sunny_suitability = Column(Float, default=0.9)
    cloudy_suitability = Column(Float, default=0.8)
    featured_image = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    destination_id = Column(Integer, ForeignKey("destinations.id"), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    sentiment_score = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    destination = relationship("Destination", backref="reviews")
    user = relationship("User", backref="reviews", lazy="joined")
class UserTrip(Base):
    __tablename__ = "user_trips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    city = Column(String(100), nullable=False)
    total_days = Column(Integer, default=3)
    pacing = Column(String(20), default="relax")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    stops = relationship("TripStop", backref="trip", cascade="all, delete-orphan")


class TripStop(Base):
    __tablename__ = "trip_stops"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    trip_id = Column(Integer, ForeignKey("user_trips.id", ondelete="CASCADE"), nullable=False)
    day_number = Column(Integer, nullable=False)
    stop_order = Column(Integer, nullable=False)
    destination_id = Column(BigInteger, ForeignKey("destinations.id"), nullable=True)
    custom_name = Column(String(200), nullable=True)
    time_slot = Column(String(50), default="08:00 - 10:00")
    time_tag = Column(String(50), default="Buổi sáng")
    custom_description = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    destination = relationship("Destination", lazy="joined")
class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    destination_id = Column(BigInteger, ForeignKey("destinations.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    destination = relationship("Destination", lazy="joined")