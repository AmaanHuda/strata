"""Initial database migration: PostGIS, Users, Parcels, Buildings, Floors, Units, ULPIN, Jobs, Datasets, Provenance, Audit.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-12 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, default='viewer'),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, default=0),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])

    # 3. Refresh tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(128), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_rt_token_hash', 'refresh_tokens', ['token_hash'])

    # 4. Parcels table
    op.create_table(
        'parcels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parcel_number', sa.String(100), unique=True, nullable=False),
        sa.Column('survey_number', sa.String(100), nullable=True),
        sa.Column('district', sa.String(100), nullable=False),
        sa.Column('taluk', sa.String(100), nullable=True),
        sa.Column('village', sa.String(100), nullable=True),
        sa.Column('state', sa.String(100), nullable=False, default='India'),
        sa.Column('land_use', sa.String(100), nullable=True),
        sa.Column('official_ulpin', sa.String(30), nullable=True),
        sa.Column('candidate_ulpin', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='CANDIDATE'),
        sa.Column('geometry_2d', geoalchemy2.types.Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=True),
        sa.Column('boundary_wkt', sa.Text(), nullable=True),
        sa.Column('source_crs', sa.String(50), nullable=False, default='EPSG:4326'),
        sa.Column('processing_crs', sa.String(50), nullable=False, default='EPSG:3857'),
        sa.Column('elevation_min_m', sa.Float(), nullable=True),
        sa.Column('elevation_max_m', sa.Float(), nullable=True),
        sa.Column('area_sqm', sa.Numeric(18, 4), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('confidence_score', sa.Float(), nullable=False, default=1.0),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_parcels_geom', 'parcels', ['geometry_2d'], postgresql_using='gist')
    op.create_index('idx_parcels_official_ulpin', 'parcels', ['official_ulpin'])
    op.create_index('idx_parcels_candidate_ulpin', 'parcels', ['candidate_ulpin'])

    # 5. Buildings table
    op.create_table(
        'buildings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('parcel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parcels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('building_name', sa.String(255), nullable=True),
        sa.Column('building_type', sa.String(100), nullable=True),
        sa.Column('floor_count', sa.Integer(), nullable=True),
        sa.Column('floor_count_above_ground', sa.Integer(), nullable=True),
        sa.Column('floor_count_below_ground', sa.Integer(), nullable=True),
        sa.Column('height_m', sa.Float(), nullable=True),
        sa.Column('height_confidence', sa.Float(), nullable=True),
        sa.Column('uncertainty_range_m', sa.Float(), nullable=True),
        sa.Column('footprint_2d', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326), nullable=True),
        sa.Column('footprint_wkt', sa.Text(), nullable=True),
        sa.Column('geometry_3d_lod2', geoalchemy2.types.Geometry(geometry_type='POLYHEDRALSURFACEZ', srid=4326), nullable=True),
        sa.Column('footprint_area_sqm', sa.Numeric(18, 4), nullable=True),
        sa.Column('volume_cum', sa.Numeric(18, 4), nullable=True),
        sa.Column('source_crs', sa.String(50), nullable=False, default='EPSG:4326'),
        sa.Column('processing_crs', sa.String(50), nullable=False, default='EPSG:3857'),
        sa.Column('official_ulpin', sa.String(30), nullable=True),
        sa.Column('candidate_ulpin', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='CANDIDATE'),
        sa.Column('ml_derived', sa.Boolean(), nullable=False, default=False),
        sa.Column('ml_model_version', sa.String(100), nullable=True),
        sa.Column('ml_confidence_score', sa.Float(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('construction_year', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_buildings_footprint', 'buildings', ['footprint_2d'], postgresql_using='gist')

    # 6. Floors table
    op.create_table(
        'floors',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('building_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('buildings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('floor_number', sa.Integer(), nullable=False),
        sa.Column('floor_label', sa.String(50), nullable=True),
        sa.Column('floor_use', sa.String(100), nullable=True),
        sa.Column('height_above_ground_m', sa.Float(), nullable=True),
        sa.Column('ceiling_height_m', sa.Float(), nullable=True),
        sa.Column('floor_area_sqm', sa.Numeric(18, 4), nullable=True),
        sa.Column('volume_cum', sa.Numeric(18, 4), nullable=True),
        sa.Column('geometry_3d', geoalchemy2.types.Geometry(geometry_type='POLYHEDRALSURFACEZ', srid=4326), nullable=True),
        sa.Column('official_ulpin', sa.String(30), nullable=True),
        sa.Column('candidate_ulpin', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='CANDIDATE'),
        sa.Column('ml_derived', sa.Boolean(), nullable=False, default=False),
        sa.Column('ml_confidence_score', sa.Float(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_floors_bld_num', 'floors', ['building_id', 'floor_number'], unique=True)

    # 7. Units table
    op.create_table(
        'units',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('floor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('floors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_number', sa.String(50), nullable=False),
        sa.Column('unit_type', sa.String(100), nullable=True),
        sa.Column('area_sqm', sa.Numeric(18, 4), nullable=True),
        sa.Column('volume_cum', sa.Numeric(18, 4), nullable=True),
        sa.Column('is_occupied', sa.Boolean(), nullable=True),
        sa.Column('geometry_3d', geoalchemy2.types.Geometry(geometry_type='POLYHEDRALSURFACEZ', srid=4326), nullable=True),
        sa.Column('official_ulpin', sa.String(30), nullable=True),
        sa.Column('candidate_ulpin', sa.String(50), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='CANDIDATE'),
        sa.Column('ml_derived', sa.Boolean(), nullable=False, default=False),
        sa.Column('ml_confidence_score', sa.Float(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_units_flr_num', 'units', ['floor_id', 'unit_number'], unique=True)

    # 8. ULPIN Registry table
    op.create_table(
        'ulpin_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('candidate_ulpin', sa.String(60), unique=True, nullable=False),
        sa.Column('official_ulpin', sa.String(30), unique=True, nullable=True),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, default='CANDIDATE'),
        sa.Column('parcel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('parcels.id', ondelete='SET NULL'), nullable=True),
        sa.Column('building_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('buildings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('floor_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('floors.id', ondelete='SET NULL'), nullable=True),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('generation_method', sa.String(50), nullable=False),
        sa.Column('confidence_score', sa.String(20), nullable=True, default='MEDIUM'),
        sa.Column('is_authoritative', sa.Boolean(), nullable=False, default=False),
        sa.Column('legal_disclaimer', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_ulpin_candidate', 'ulpin_records', ['candidate_ulpin'])
    op.create_index('idx_ulpin_official', 'ulpin_records', ['official_ulpin'])

    # 9. Async Jobs table
    op.create_table(
        'async_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_type', sa.String(100), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='QUEUED'),
        sa.Column('progress', sa.Float(), nullable=False, default=0.0),
        sa.Column('progress_message', sa.Text(), nullable=True),
        sa.Column('payload', postgresql.JSONB(), nullable=True),
        sa.Column('result', postgresql.JSONB(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_retries', sa.Integer(), nullable=False, default=3),
        sa.Column('idempotency_key', sa.String(255), unique=True, nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('model_name', sa.String(100), nullable=True),
        sa.Column('model_version', sa.String(100), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_jobs_status', 'async_jobs', ['status'])
    op.create_index('idx_jobs_idempotency', 'async_jobs', ['idempotency_key'])

    # 10. Dataset Registry table
    op.create_table(
        'dataset_registry',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('version', sa.String(50), nullable=False, default='1.0.0'),
        sa.Column('source', sa.String(500), nullable=True),
        sa.Column('license', sa.String(255), nullable=True),
        sa.Column('modality', sa.String(100), nullable=True),
        sa.Column('crs', sa.String(50), nullable=True),
        sa.Column('resolution_m', sa.String(50), nullable=True),
        sa.Column('coverage_area', sa.Text(), nullable=True),
        sa.Column('record_count', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ingested_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_dataset_name', 'dataset_registry', ['name'])

    # 11. Provenance Records table
    op.create_table(
        'provenance_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('data_source', sa.String(255), nullable=False),
        sa.Column('derivation_method', sa.String(100), nullable=False),
        sa.Column('input_datasets', postgresql.JSONB(), nullable=True),
        sa.Column('model_version', sa.String(100), nullable=True),
        sa.Column('input_hash', sa.String(128), nullable=True),
        sa.Column('confidence_label', sa.String(20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_prov_entity', 'provenance_records', ['entity_type', 'entity_id'])

    # 12. Audit Logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operation', sa.String(20), nullable=False),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('before_data', postgresql.JSONB(), nullable=True),
        sa.Column('after_data', postgresql.JSONB(), nullable=True),
        sa.Column('diff', postgresql.JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_audit_table_rec', 'audit_logs', ['table_name', 'record_id'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('provenance_records')
    op.drop_table('dataset_registry')
    op.drop_table('async_jobs')
    op.drop_table('ulpin_records')
    op.drop_table('units')
    op.drop_table('floors')
    op.drop_table('buildings')
    op.drop_table('parcels')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
