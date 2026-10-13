"""Prepare/verify only an explicitly approved disposable PostgreSQL test target."""

import argparse
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from psycopg import sql
from sqlalchemy import URL, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from app.db import create_database_engine, database_url

TEST_DATABASE = "supplier_invoice_verification_test"
TEST_USER = TEST_DATABASE
PROJECT_PATTERN = re.compile(
    r"supplier-invoice-verification-(?:check-[0-9a-f]{32}|ci-[1-9][0-9]*-[1-9][0-9]*)"
)
MARKER_PREFIX = "Supplier-Invoice-Verification disposable schema tests: "
BACKEND_ROOT = Path(__file__).resolve().parents[1]


class TestTargetError(RuntimeError):
    __test__ = False


def approved_test_url(settings: Mapping[str, str]) -> URL:
    """Reject missing settings and development defaults before opening a connection."""
    if settings.get("RUN_POSTGRES_TESTS") != "1":
        raise TestTargetError("PostgreSQL schema tests require RUN_POSTGRES_TESTS=1.")
    if not PROJECT_PATTERN.fullmatch(settings.get("POSTGRES_TEST_PROJECT", "")):
        raise TestTargetError("An approved unique disposable Compose project is required.")
    required = {
        "POSTGRES_DB": TEST_DATABASE,
        "POSTGRES_USER": TEST_USER,
        "POSTGRES_HOST": "db",
        "POSTGRES_PORT": "5432",
    }
    if any(settings.get(key) != value for key, value in required.items()):
        raise TestTargetError("Refusing a database target outside the disposable test settings.")
    if not settings.get("POSTGRES_PASSWORD", "").strip():
        raise TestTargetError("An explicit disposable database password is required.")
    return database_url(settings)


def expected_marker(settings: Mapping[str, str]) -> str:
    approved_test_url(settings)
    return MARKER_PREFIX + settings["POSTGRES_TEST_PROJECT"]


def validate_connected_target(connection: Connection) -> None:
    database, user, version = connection.execute(
        text("SELECT current_database(), current_user, current_setting('server_version_num')::integer")
    ).one()
    if database != TEST_DATABASE or user != TEST_USER or not 170000 <= version < 180000:
        raise TestTargetError("Connected database/user/version is not the approved PostgreSQL 17 test target.")


def database_marker(connection: Connection) -> str | None:
    return connection.execute(text(
        "SELECT shobj_description(oid, 'pg_database') "
        "FROM pg_database WHERE datname = current_database()"
    )).scalar_one()


def require_test_marker(connection: Connection, settings: Mapping[str, str]) -> None:
    marker = expected_marker(settings)
    validate_connected_target(connection)
    if database_marker(connection) != marker:
        raise TestTargetError("Missing or mismatched disposable database marker; refusing schema tests.")


def prepare_test_database(connection: Connection, settings: Mapping[str, str]) -> None:
    """Mark a fresh target only; never relabel a populated or foreign-marked database."""
    marker = expected_marker(settings)
    validate_connected_target(connection)
    existing = database_marker(connection)
    if existing == marker:
        return
    if existing is not None or inspect(connection).get_table_names(schema="public"):
        raise TestTargetError("Refusing to mark a nonempty or previously marked database.")
    statement = sql.SQL("COMMENT ON DATABASE {} IS {}").format(
        sql.Identifier(TEST_DATABASE), sql.Literal(marker)
    )
    connection.exec_driver_sql(statement.as_string())


def migration_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def verify_revision(connection: Connection) -> str:
    heads = ScriptDirectory.from_config(migration_config()).get_heads()
    actual = list(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
    if len(heads) != 1 or actual != heads:
        raise TestTargetError("The disposable database is not at the expected single migration head.")
    return actual[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "verify"])
    args = parser.parse_args()
    engine = None
    try:
        engine = create_database_engine(approved_test_url(os.environ))
        with engine.begin() as connection:
            if args.action == "prepare":
                prepare_test_database(connection, os.environ)
                print("Approved disposable PostgreSQL test database prepared.")
            else:
                require_test_marker(connection, os.environ)
                revision = verify_revision(connection)
                print(f"Disposable PostgreSQL migration revision: {revision} (head)")
    except TestTargetError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (SQLAlchemyError, OSError):
        print("Disposable database check failed; check service availability and migration setup.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
