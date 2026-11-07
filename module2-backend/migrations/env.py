"""Explicit upgrades only; never fall back to the root .env database."""
import os

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config


def run_migrations(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError('This data migration requires an online DATABASE_URL')
elif config.attributes.get('connection') is not None:
    run_migrations(config.attributes['connection'])
else:
    with create_engine(os.environ['DATABASE_URL'], poolclass=pool.NullPool).connect() as connection:
        run_migrations(connection)
