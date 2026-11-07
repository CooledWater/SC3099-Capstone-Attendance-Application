"""Protect existing audit rows and backfill check-in retention deadlines.

Apply after the existing application tables have been provisioned. Fresh schemas
receive audit guards/indexes through SQLAlchemy metadata; this upgrade is still
safe to run on those schemas and never changes existing non-NULL deadlines.
"""
from datetime import timedelta

from alembic import op
import sqlalchemy as sa

revision = '20261107_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    from app.audit_storage import install_audit_guards
    connection = op.get_bind()
    install_audit_guards(connection)
    checkins = sa.Table('checkins', sa.MetaData(), autoload_with=connection)
    sa.Index('ix_checkins_scheduled_deletion_at', checkins.c.scheduled_deletion_at).create(connection, checkfirst=True)
    while True:
        rows = connection.execute(sa.select(checkins.c.id, checkins.c.checked_in_at).where(
            checkins.c.scheduled_deletion_at.is_(None),
        ).limit(500)).all()
        if not rows:
            break
        connection.execute(checkins.update().where(
            checkins.c.id == sa.bindparam('_checkin_id'), checkins.c.scheduled_deletion_at.is_(None),
        ).values(scheduled_deletion_at=sa.bindparam('_deadline')), [
            {'_checkin_id': identity, '_deadline': checked_in_at + timedelta(days=30)}
            for identity, checked_in_at in rows
        ])


def downgrade():
    raise RuntimeError('Audit immutability and retention deadlines cannot be removed by downgrade')
