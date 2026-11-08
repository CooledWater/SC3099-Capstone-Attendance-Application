"""Enable app-consent defaults for future accounts, preserving existing choices.

Explicitly authorized policy override of the recommended FALSE defaults.
No existing consent value is updated, including prior revocations.
"""
from alembic import op
import sqlalchemy as sa

revision = '20261108_02'
down_revision = '20261107_01'
branch_labels = None
depends_on = None


def upgrade():
    for field in ('camera_consent', 'geolocation_consent'):
        op.alter_column('users', field, existing_type=sa.Boolean(), server_default=sa.true())


def downgrade():
    for field in ('camera_consent', 'geolocation_consent'):
        op.alter_column('users', field, existing_type=sa.Boolean(), server_default=sa.false())
