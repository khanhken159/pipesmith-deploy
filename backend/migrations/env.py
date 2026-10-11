"""Alembic environment; schema changes require the dedicated migration account."""

from alembic import context
from sqlalchemy import create_engine, pool

from src.config import get_settings
from src.services.auth import Base, check_database_url

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    settings = get_settings()
    url = config.get_main_option("sqlalchemy.url") or settings.migration_database_url
    if not url:
        raise RuntimeError("MIGRATION_DATABASE_URL is required to run migrations.")
    check_database_url(url, settings.app_env)
    return url


def run_migrations_offline() -> None:
    """Sinh SQL ra màn hình (`alembic upgrade head --sql`) để người duyệt xem trước khi chạy thật."""
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Chạy migration trên cơ sở dữ liệu."""
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
