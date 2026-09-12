"""Core property hierarchy: Parcel â†’ Building â†’ Floor â†’ Unit."""
import uuid
from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey,
                         Integer, Numeric, String, Text, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class Parcel(Base):
    """Land parcel â€” the root spatial entity."""
    __tablename__ = "parcels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_number = Column(String(100), unique=True, nullable=False, index=True)
    survey_number = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=False, index=True)
    taluk = Column(String(100), nullable=True)
    village = Column(String(100), nullable=True)
    state = Column(String(100), nullable=False, default="India")
    land_use = Column(String(100), nullable=True)
    area_sqm = Column(Numeric(18, 4), nullable=True)
    geometry_2d = Column(Geometry("POLYGON", srid=4326), nullable=True)
    geometry_3d = Column(Geometry("POLYGONZ", srid=4326), nullable=True)
    elevation_min_m = Column(Float, nullable=True)
    elevation_max_m = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.now(timezone.utc), nullable=False)
    version = Column(Integer, default=1, nullable=False)

    buildings = relationship("Building", back_populates="parcel", cascade="all, delete-orphan")
    ulpin_records = relationship("ULPINRecord", back_populates="parcel")

    def __repr__(self) -> str:
        return f"<Parcel {self.parcel_number}>"


class Building(Base):
    """Building on a parcel."""
    __tablename__ = "buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_id = Column(UUID(as_uuid=True), ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    building_name = Column(String(255), nullable=True)
    building_type = Column(String(100), nullable=True)  # residential, commercial, mixed
    floor_count = Column(Integer, nullable=True)
    floor_count_above_ground = Column(Integer, nullable=True)
    floor_count_below_ground = Column(Integer, nullable=True)
    height_m = Column(Float, nullable=True)
    height_confidence = Column(Float, nullable=True)  # 0-1 ML confidence
    footprint_2d = Column(Geometry("POLYGON", srid=4326), nullable=True)
    geometry_3d = Column(Geometry("POLYHEDRALSURFACEZ", srid=4326), nullable=True)
    footprint_area_sqm = Column(Numeric(18, 4), nullable=True)
    construction_year = Column(Integer, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    ml_derived = Column(Boolean, default=False, nullable=False)
    ml_model_version = Column(String(50), nullable=True)
    ml_confidence_score = Column(Float, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.now(timezone.utc), nullable=False)
    version = Column(Integer, default=1, nullable=False)

    parcel = relationship("Parcel", back_populates="buildings")
    floors = relationship("Floor", back_populates="building", cascade="all, delete-orphan", order_by="Floor.floor_number")

    def __repr__(self) -> str:
        return f"<Building id={self.id} parcel={self.parcel_id}>"


class Floor(Base):
    """A floor (storey) within a building."""
    __tablename__ = "floors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    building_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number = Column(Integer, nullable=False)  # -1=basement, 0=ground, 1=first, â€¦
    floor_label = Column(String(50), nullable=True)  # "G", "1st", "B1"
    floor_use = Column(String(100), nullable=True)
    height_above_ground_m = Column(Float, nullable=True)
    ceiling_height_m = Column(Float, nullable=True)
    floor_area_sqm = Column(Numeric(18, 4), nullable=True)
    geometry_3d = Column(Geometry("POLYHEDRALSURFACEZ", srid=4326), nullable=True)
    ml_derived = Column(Boolean, default=False, nullable=False)
    ml_confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.now(timezone.utc), nullable=False)

    building = relationship("Building", back_populates="floors")
    units = relationship("Unit", back_populates="floor", cascade="all, delete-orphan")
    ulpin_records = relationship("ULPINRecord", back_populates="floor")


class Unit(Base):
    """A discrete property unit (apartment, shop, office)."""
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    floor_id = Column(UUID(as_uuid=True), ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_number = Column(String(50), nullable=False)
    unit_type = Column(String(100), nullable=True)  # residential, commercial, common
    area_sqm = Column(Numeric(18, 4), nullable=True)
    geometry_3d = Column(Geometry("POLYHEDRALSURFACEZ", srid=4326), nullable=True)
    owner_name = Column(String(255), nullable=True)
    owner_contact = Column(String(255), nullable=True)
    is_occupied = Column(Boolean, nullable=True)
    ml_derived = Column(Boolean, default=False, nullable=False)
    ml_confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=datetime.now(timezone.utc), nullable=False)

    floor = relationship("Floor", back_populates="units")
    ulpin_records = relationship("ULPINRecord", back_populates="unit")
