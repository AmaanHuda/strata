"""
Property hierarchy models: Parcel -> Building -> Floor -> Unit.
Strict privacy: NO owner names, contact numbers, or private ownership IDs.
Temporal versioning: version, valid_from, valid_to, is_active, deleted_at.
Scientific ML states: DERIVED, INFERRED, CANDIDATE, DATA_LIMITED, CONFLICTING, AUTHORITATIVE.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer,
    Numeric, String, Text, text, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


class ScientificStatus:
    CANDIDATE = "CANDIDATE"
    PROPOSED = "PROPOSED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    DATA_LIMITED = "DATA_LIMITED"
    CONFLICTING = "CONFLICTING"
    AUTHORITATIVE = "AUTHORITATIVE"
    SUPPORTED = "SUPPORTED"
    MISSING = "MISSING"


class Parcel(Base):
    """
    A 2D cadastral land parcel. Base entity for all buildings.
    No private ownership data is stored or exposed.
    """
    __tablename__ = "parcels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_number = Column(String(100), unique=True, nullable=False, index=True)
    survey_number = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=False, index=True)
    taluk = Column(String(100), nullable=True, index=True)
    village = Column(String(100), nullable=True, index=True)
    state = Column(String(100), nullable=False, default="India")
    land_use = Column(String(100), nullable=True)

    # Official vs Candidate ULPIN (Official is nullable, never fabricated)
    official_ulpin = Column(String(30), nullable=True, index=True)
    candidate_ulpin = Column(String(50), nullable=True, index=True)
    status = Column(String(50), default=ScientificStatus.CANDIDATE, nullable=False)

    # Geometry - 2D footprint in EPSG:4326
    geometry_2d = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    boundary_wkt = Column(Text, nullable=True)
    source_crs = Column(String(50), default="EPSG:4326", nullable=False)
    processing_crs = Column(String(50), default="EPSG:3857", nullable=False)

    # Elevation & Area (metric calculated via projected CRS)
    elevation_min_m = Column(Float, nullable=True)
    elevation_max_m = Column(Float, nullable=True)
    area_sqm = Column(Numeric(18, 4), nullable=True)

    # Verification & Lineage
    is_verified = Column(Boolean, default=False, nullable=False)
    confidence_score = Column(Float, default=1.0, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Temporal Versioning & Lifecycle
    version = Column(Integer, default=1, nullable=False)
    valid_from = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    buildings = relationship("Building", back_populates="parcel", cascade="all, delete-orphan")
    ulpin_records = relationship("ULPINRecord", back_populates="parcel")

    def expire(self):
        """Expire the current version."""
        self.valid_to = datetime.now(timezone.utc)
        self.is_active = False

    def create_new_version(self):
        """Create a new version based on this one."""
        self.expire()
        new_parcel = Parcel(
            parcel_number=self.parcel_number,
            survey_number=self.survey_number,
            district=self.district,
            taluk=self.taluk,
            village=self.village,
            state=self.state,
            land_use=self.land_use,
            official_ulpin=self.official_ulpin,
            candidate_ulpin=self.candidate_ulpin,
            status=self.status,
            geometry_2d=self.geometry_2d,
            boundary_wkt=self.boundary_wkt,
            source_crs=self.source_crs,
            processing_crs=self.processing_crs,
            elevation_min_m=self.elevation_min_m,
            elevation_max_m=self.elevation_max_m,
            area_sqm=self.area_sqm,
            is_verified=self.is_verified,
            confidence_score=self.confidence_score,
            metadata_=self.metadata_,
            version=self.version + 1,
            valid_from=datetime.now(timezone.utc),
            is_active=True
        )
        return new_parcel

    __table_args__ = (
        Index("idx_parcels_geom", "geometry_2d", postgresql_using="gist"),
        Index("idx_parcels_district_village", "district", "village"),
    )


class Building(Base):
    """
    A 3D building entity sitting on a land parcel.
    Contains vertical floor hierarchy and 3D bounding geometry.
    """
    __tablename__ = "buildings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parcel_id = Column(UUID(as_uuid=True), ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    building_name = Column(String(255), nullable=True)
    building_type = Column(String(100), nullable=True)  # residential, commercial, mixed, industrial

    # Height and floors
    floor_count = Column(Integer, nullable=True)
    floor_count_above_ground = Column(Integer, nullable=True)
    floor_count_below_ground = Column(Integer, nullable=True)
    height_m = Column(Float, nullable=True)
    height_confidence = Column(Float, nullable=True)
    uncertainty_range_m = Column(Float, nullable=True)

    # Geometry
    footprint_2d = Column(Geometry("POLYGON", srid=4326), nullable=True)
    footprint_wkt = Column(Text, nullable=True)
    geometry_3d_lod2 = Column(Geometry("POLYHEDRALSURFACEZ", srid=4326), nullable=True)
    footprint_area_sqm = Column(Numeric(18, 4), nullable=True)
    volume_cum = Column(Numeric(18, 4), nullable=True)
    source_crs = Column(String(50), default="EPSG:4326", nullable=False)
    processing_crs = Column(String(50), default="EPSG:3857", nullable=False)

    # Identifiers (official is nullable, candidate is non-authoritative)
    official_ulpin = Column(String(30), nullable=True, index=True)
    candidate_ulpin = Column(String(50), nullable=True, index=True)
    status = Column(String(50), default=ScientificStatus.CANDIDATE, nullable=False)

    # ML & Extraction Provenance
    ml_derived = Column(Boolean, default=False, nullable=False)
    ml_model_version = Column(String(100), nullable=True)
    ml_confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    construction_year = Column(Integer, nullable=True)
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Temporal Versioning & Lifecycle
    version = Column(Integer, default=1, nullable=False)
    valid_from = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    parcel = relationship("Parcel", back_populates="buildings")
    floors = relationship("Floor", back_populates="building", cascade="all, delete-orphan", order_by="Floor.floor_number")
    ulpin_records = relationship("ULPINRecord", back_populates="building")

    def expire(self):
        """Expire the current version."""
        self.valid_to = datetime.now(timezone.utc)
        self.is_active = False

    def create_new_version(self):
        """Create a new version based on this one."""
        self.expire()
        new_bld = Building(
            parcel_id=self.parcel_id,
            building_name=self.building_name,
            building_type=self.building_type,
            floor_count=self.floor_count,
            floor_count_above_ground=self.floor_count_above_ground,
            floor_count_below_ground=self.floor_count_below_ground,
            height_m=self.height_m,
            height_confidence=self.height_confidence,
            uncertainty_range_m=self.uncertainty_range_m,
            footprint_2d=self.footprint_2d,
            footprint_wkt=self.footprint_wkt,
            geometry_3d_lod2=self.geometry_3d_lod2,
            footprint_area_sqm=self.footprint_area_sqm,
            volume_cum=self.volume_cum,
            source_crs=self.source_crs,
            processing_crs=self.processing_crs,
            official_ulpin=self.official_ulpin,
            candidate_ulpin=self.candidate_ulpin,
            status=self.status,
            ml_derived=self.ml_derived,
            ml_model_version=self.ml_model_version,
            ml_confidence_score=self.ml_confidence_score,
            is_verified=self.is_verified,
            construction_year=self.construction_year,
            metadata_=self.metadata_,
            version=self.version + 1,
            valid_from=datetime.now(timezone.utc),
            is_active=True
        )
        return new_bld

    __table_args__ = (
        Index("idx_buildings_footprint", "footprint_2d", postgresql_using="gist"),
        CheckConstraint("floor_count IS NULL OR floor_count >= 0", name="chk_positive_floor_count"),
        CheckConstraint("height_m IS NULL OR height_m >= 0", name="chk_positive_height"),
    )


class Floor(Base):
    """
    A single vertical level within a building.
    Floor numbering: -1=basement, 0=ground, 1=1st floor, etc.
    """
    __tablename__ = "floors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    building_id = Column(UUID(as_uuid=True), ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False, index=True)
    floor_number = Column(Integer, nullable=False)
    floor_label = Column(String(50), nullable=True)  # "G", "1st", "B1"
    floor_use = Column(String(100), nullable=True)

    # Vertical coordinates (metric meters)
    height_above_ground_m = Column(Float, nullable=True)
    ceiling_height_m = Column(Float, nullable=True)
    floor_area_sqm = Column(Numeric(18, 4), nullable=True)
    volume_cum = Column(Numeric(18, 4), nullable=True)

    # 3D bounding geometry
    geometry_3d = Column(Geometry("POLYHEDRALSURFACEZ", srid=4326), nullable=True)

    # Identifiers
    official_ulpin = Column(String(30), nullable=True, index=True)
    candidate_ulpin = Column(String(50), nullable=True, index=True)
    status = Column(String(50), default=ScientificStatus.CANDIDATE, nullable=False)

    # ML & Verification
    ml_derived = Column(Boolean, default=False, nullable=False)
    ml_confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Temporal Versioning & Lifecycle
    version = Column(Integer, default=1, nullable=False)
    valid_from = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    building = relationship("Building", back_populates="floors")
    units = relationship("Unit", back_populates="floor", cascade="all, delete-orphan", order_by="Unit.unit_number")
    ulpin_records = relationship("ULPINRecord", back_populates="floor")

    def expire(self):
        """Expire the current version."""
        self.valid_to = datetime.now(timezone.utc)
        self.is_active = False

    def create_new_version(self):
        """Create a new version based on this one."""
        self.expire()
        new_floor = Floor(
            building_id=self.building_id,
            floor_number=self.floor_number,
            floor_label=self.floor_label,
            floor_use=self.floor_use,
            height_above_ground_m=self.height_above_ground_m,
            ceiling_height_m=self.ceiling_height_m,
            floor_area_sqm=self.floor_area_sqm,
            volume_cum=self.volume_cum,
            geometry_3d=self.geometry_3d,
            official_ulpin=self.official_ulpin,
            candidate_ulpin=self.candidate_ulpin,
            status=self.status,
            ml_derived=self.ml_derived,
            ml_confidence_score=self.ml_confidence_score,
            is_verified=self.is_verified,
            metadata_=self.metadata_,
            version=self.version + 1,
            valid_from=datetime.now(timezone.utc),
            is_active=True
        )
        return new_floor

    __table_args__ = (
        Index("idx_floors_bld_num", "building_id", "floor_number", unique=True),
    )


class Unit(Base):
    """
    A discrete vertical property unit (apartment, office, shop, common utility space).
    No private ownership data stored.
    """
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    floor_id = Column(UUID(as_uuid=True), ForeignKey("floors.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_number = Column(String(50), nullable=False)
    unit_type = Column(String(100), nullable=True)  # residential, commercial, common_utility
    area_sqm = Column(Numeric(18, 4), nullable=True)
    volume_cum = Column(Numeric(18, 4), nullable=True)
    is_occupied = Column(Boolean, nullable=True)

    # 3D bounding geometry
    geometry_3d = Column(Geometry("POLYHEDRALSURFACEZ", srid=4326), nullable=True)

    # Identifiers
    official_ulpin = Column(String(30), nullable=True, index=True)
    candidate_ulpin = Column(String(50), nullable=True, index=True)
    status = Column(String(50), default=ScientificStatus.CANDIDATE, nullable=False)

    # ML & Verification
    ml_derived = Column(Boolean, default=False, nullable=False)
    ml_confidence_score = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=True)

    # Temporal Versioning & Lifecycle
    version = Column(Integer, default=1, nullable=False)
    valid_from = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=text("NOW()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("NOW()"), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    floor = relationship("Floor", back_populates="units")
    ulpin_records = relationship("ULPINRecord", back_populates="unit")

    def expire(self):
        """Expire the current version."""
        self.valid_to = datetime.now(timezone.utc)
        self.is_active = False

    def create_new_version(self):
        """Create a new version based on this one."""
        self.expire()
        new_unit = Unit(
            floor_id=self.floor_id,
            unit_number=self.unit_number,
            unit_type=self.unit_type,
            area_sqm=self.area_sqm,
            volume_cum=self.volume_cum,
            is_occupied=self.is_occupied,
            geometry_3d=self.geometry_3d,
            official_ulpin=self.official_ulpin,
            candidate_ulpin=self.candidate_ulpin,
            status=self.status,
            ml_derived=self.ml_derived,
            ml_confidence_score=self.ml_confidence_score,
            is_verified=self.is_verified,
            metadata_=self.metadata_,
            version=self.version + 1,
            valid_from=datetime.now(timezone.utc),
            is_active=True
        )
        return new_unit

    __table_args__ = (
        Index("idx_units_flr_num", "floor_id", "unit_number", unique=True),
        CheckConstraint("area_sqm IS NULL OR area_sqm > 0", name="chk_positive_unit_area"),
    )
