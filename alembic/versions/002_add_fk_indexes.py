"""Add missing foreign-key indexes for join and spatial lookup paths.

The GiST spatial indexes (idx_buildings_footprint, idx_parcels_geom) are created in
001_initial_schema. The FK columns used by the point-lookup / structure joins
(buildings.parcel_id, floors.building_id, units.floor_id) were only covered by
composite unique indexes, so single-column FK lookups fell back to sequential scans.

All statements are IF NOT EXISTS, so this migration is safe to run on databases
that were created before it (and re-runnable by hand if a DB is partially migrated).

Revision ID: 002_fk_indexes
Revises: 001_initial_schema
Create Date: 2026-09-25
"""
from alembic import op

revision = "002_fk_indexes"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_buildings_parcel_id ON buildings (parcel_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_floors_building_id ON floors (building_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_units_floor_id ON units (floor_id);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_units_floor_id;")
    op.execute("DROP INDEX IF EXISTS idx_floors_building_id;")
    op.execute("DROP INDEX IF EXISTS idx_buildings_parcel_id;")
