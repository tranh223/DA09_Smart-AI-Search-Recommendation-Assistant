"""
SQLAlchemy ORM models — mirrors the public schema in Supabase.

All relationships are defined so callers can do selectinload() for eager
loading in a single round-trip instead of N+1 queries.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Association table: hotels ↔ amenities ──────────────────────────────────
hotel_amenities_table = Table(
    "hotel_amenities",
    Base.metadata,
    Column("hotel_id", Integer, ForeignKey("hotels.id"), primary_key=True),
    Column("amenity_id", Integer, ForeignKey("amenities.id"), primary_key=True),
)


class HotelModel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    property_type = Column(String)
    accommodation_type = Column(String)
    star_rating = Column(Numeric)
    is_luxury = Column(Boolean, default=False)
    review_score = Column(Numeric)
    review_count = Column(Integer, default=0)
    address = Column(Text)
    city = Column(String)
    city_id = Column(Integer)
    area = Column(String)
    country = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    description = Column(Text)
    source_url = Column(Text)

    # Relationships
    images = relationship("HotelImageModel", back_populates="hotel", lazy="select")
    policy = relationship("HotelPolicyModel", back_populates="hotel", uselist=False, lazy="select")
    reviews = relationship("ReviewModel", back_populates="hotel", lazy="select")
    suitability = relationship("HotelSuitabilityModel", back_populates="hotel", lazy="select")
    review_aspects = relationship("ReviewAspectModel", back_populates="hotel", lazy="select")
    review_grades = relationship("ReviewGradeModel", back_populates="hotel", lazy="select")
    amenities = relationship("AmenityModel", secondary=hotel_amenities_table, back_populates="hotels", lazy="select")
    rooms = relationship("RoomModel", back_populates="hotel", lazy="select")
    nearby_places = relationship("NearbyPlaceModel", back_populates="hotel", lazy="select")
    activities = relationship("ActivityModel", back_populates="hotel", lazy="select")


class HotelImageModel(Base):
    __tablename__ = "hotel_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    url = Column(Text, nullable=False)
    is_primary = Column(Boolean, default=False)

    hotel = relationship("HotelModel", back_populates="images")


class HotelPolicyModel(Base):
    __tablename__ = "hotel_policies"

    hotel_id = Column(Integer, ForeignKey("hotels.id"), primary_key=True)
    check_in_from = Column(String)
    check_out_until = Column(String)
    service_fee_pct = Column(Numeric, default=0.00)
    child_policy = Column(Text)
    pet_policy = Column(Text)
    deposit_required = Column(Boolean, default=False)
    policy_notes = Column(ARRAY(Text))

    hotel = relationship("HotelModel", back_populates="policy")


class ReviewModel(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    reviewer_name = Column(String)
    reviewer_country = Column(String)
    rating = Column(Numeric)
    review_date = Column(Date)
    title = Column(Text)
    text = Column(Text, nullable=False)
    positive_text = Column(Text)
    negative_text = Column(Text)

    hotel = relationship("HotelModel", back_populates="reviews")


class HotelSuitabilityModel(Base):
    __tablename__ = "hotel_suitability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    suitable_for_tag = Column(String, nullable=False)
    mention_count = Column(Integer)
    score = Column(Numeric)

    hotel = relationship("HotelModel", back_populates="suitability")


class ReviewAspectModel(Base):
    __tablename__ = "review_aspects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    aspect_name = Column(String, nullable=False)
    mentioned = Column(Integer)
    positive_pct = Column(Numeric)

    hotel = relationship("HotelModel", back_populates="review_aspects")


class ReviewGradeModel(Base):
    __tablename__ = "review_grades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    grade_name = Column(String, nullable=False)
    grade_score = Column(Numeric)

    hotel = relationship("HotelModel", back_populates="review_grades")


class AmenityCategoryModel(Base):
    __tablename__ = "amenity_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)

    amenities = relationship("AmenityModel", back_populates="category_rel")


class AmenityModel(Base):
    __tablename__ = "amenities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String)
    category_id = Column(Integer, ForeignKey("amenity_categories.id"))

    category_rel = relationship("AmenityCategoryModel", back_populates="amenities")
    hotels = relationship("HotelModel", secondary=hotel_amenities_table, back_populates="amenities")


class RoomModel(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    room_type_id = Column(BigInteger)
    name = Column(String, nullable=False)
    price = Column(Numeric)
    room_size = Column(String)
    max_occupancy = Column(Integer)
    bed_type = Column(String)
    room_view = Column(String)
    room_amenities = Column(ARRAY(Text))
    images = Column(ARRAY(Text))
    review_score = Column(Numeric)

    hotel = relationship("HotelModel", back_populates="rooms")


class PlaceCategoryModel(Base):
    __tablename__ = "place_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, unique=True)

    nearby_places = relationship("NearbyPlaceModel", back_populates="category_rel")


class NearbyPlaceModel(Base):
    __tablename__ = "nearby_places"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(String)
    category_id = Column(Integer, ForeignKey("place_categories.id"))
    distance_km = Column(Numeric)

    hotel = relationship("HotelModel", back_populates="nearby_places")
    category_rel = relationship("PlaceCategoryModel", back_populates="nearby_places")


class ActivityModel(Base):
    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    activity_id = Column(BigInteger)
    title = Column(String, nullable=False)
    description = Column(Text)
    price_amount = Column(Numeric)
    review_score = Column(Numeric)

    hotel = relationship("HotelModel", back_populates="activities")


class TextChunkModel(Base):
    __tablename__ = "text_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    chunk_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    # embedding column intentionally omitted (pgvector USER-DEFINED type)
    # NOTE: 'metadata' is reserved by SQLAlchemy's Declarative API, so we map it as 'chunk_metadata'
    chunk_metadata = Column("metadata", JSONB, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
