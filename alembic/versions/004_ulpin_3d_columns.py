"""Add deterministic 3D ULPIN versioning/taxonomy columns to ulpin_records.

Two additive changes:

1. ``algorithm_version`` / ``canonicalization_version`` / ``object_type`` — new
   nullable columns. Existing rows get NULL, which correctly marks them as legacy
   (pre-3D) identifiers that remain reproducible by ``app/services/ulpin.py``.
2. ``candidate_ulpin`` is widened from varchar(60) to varchar(120). The
   deterministic 3D ULPIN form
   ``3DULPIN-01-IN-{STATE}-{DISTRICT}-{PARCEL_ID}-{BUILDING_ID}-{FLOOR_CODE}-{UNIT_ID}-{CHECKSUM}``
   is 62 characters for a 2-letter state / 3-letter district and up to ~78 in the
   worst case, so varchar(60) would silently truncate/reject it.

Revision ID: 004_ulpin_3d_columns
Revises: 003_dataset_registry_columns
"""
from alembic import op
import sqlalchemy as sa

revision = '004_ulpin_3d_columns'
down_revision = '003_dataset_registry_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('ulpin_records', 'candidate_ulpin', existing_type=sa.String(60), type_=sa.String(120), existing_nullable=False)
    op.add_column('ulpin_records', sa.Column('algorithm_version', sa.String(50), nullable=True))
    op.add_column('ulpin_records', sa.Column('canonicalization_version', sa.String(30), nullable=True))
    op.add_column('ulpin_records', sa.Column('object_type', sa.String(30), nullable=True))
    op.create_index(
        'ix_ulpin_records_algorithm_version', 'ulpin_records', ['algorithm_version']
    )
    # The registry must be able to answer "does this 3D ULPIN already exist?"
    # cheaply and may not contain two live rows for the same 3D entity.
    op.create_index(
        'ix_ulpin_records_entity_algorithm',
        'ulpin_records',
        ['building_id', 'floor_id', 'unit_id', 'parcel_id', 'algorithm_version'],
    )


def downgrade() -> None:
    op.drop_index('ix_ulpin_records_entity_algorithm', table_name='ulpin_records')
    op.drop_index('ix_ulpin_records_algorithm_version', table_name='ulpin_records')
    op.drop_column('ulpin_records', 'object_type')
    op.drop_column('ulpin_records', 'canonicalization_version')
    op.drop_column('ulpin_records', 'algorithm_version')
    op.alter_column('ulpin_records', 'candidate_ulpin', existing_type=sa.String(120), type_=sa.String(60), existing_nullable=False)
