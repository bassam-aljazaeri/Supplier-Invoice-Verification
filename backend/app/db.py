"""Shared synchronous PostgreSQL configuration; no implicit schema or data writes."""

import os
from collections.abc import Iterator, Mapping

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def database_url(settings: Mapping[str, str] | None = None) -> URL:
    """Build a URL object without interpolating or logging credentials."""
    settings = os.environ if settings is None else settings
    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.get("POSTGRES_USER", "supplier_invoice"),
        password=settings.get("POSTGRES_PASSWORD", "local-only-placeholder"),
        host=settings.get("POSTGRES_HOST", "db"),
        port=int(settings.get("POSTGRES_PORT", "5432")),
        database=settings.get("POSTGRES_DB", "supplier_invoice"),
    )


def create_database_engine(url: URL | None = None) -> Engine:
    return create_engine(
        database_url() if url is None else url,
        connect_args={"connect_timeout": 2},
        pool_timeout=3,
        pool_pre_ping=True,
        hide_parameters=True,
    )


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Own one request's session; callers explicitly commit business writes."""
    session = SessionLocal()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    finally:
        # Closing also rolls back any successful request's uncommitted work.
        session.close()
