"""Alembic environment. Migrations are raw SQL, so there is no autogenerate."""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings, normalize_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _database_url() -> str:
    # 테스트 등에서 Config.set_main_option("sqlalchemy.url", ...) 로 덮어쓸 수 있다.
    explicit = config.get_main_option("sqlalchemy.url")
    return normalize_database_url(explicit) if explicit else get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL without connecting."""
    context.configure(url=_database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
