"""Add dataset_registry columns expected by ORM: authority, acquisition_date, validation_status.

Revision ID: 003_dataset_registry_columns
Revises: 002_fk_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = '003_dataset_registry_columns'
down_revision = '002_fk_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('dataset_registry', sa.Column('authority', sa.String(255), nullable=True))
    op.add_column('dataset_registry', sa.Column('acquisition_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('dataset_registry', sa.Column('validation_status', sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column('dataset_registry', 'validation_status')
    op.drop_column('dataset_registry', 'acquisition_date')
    op.drop_column('dataset_registry', 'authority')
