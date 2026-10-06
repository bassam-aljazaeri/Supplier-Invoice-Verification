import os
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Response
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def database_url() -> URL:
    """Build a PostgreSQL URL safely from separate connection settings."""
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "supplier_invoice"),
        password=os.getenv("POSTGRES_PASSWORD", "local-only-placeholder"),
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "supplier_invoice"),
    )


engine = create_engine(
    database_url(),
    connect_args={"connect_timeout": 2},
    pool_timeout=3,
    pool_pre_ping=True,
)


def create_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        socket_connect_timeout=1,
        socket_timeout=1,
        health_check_interval=30,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = create_redis_client()
    try:
        yield
    finally:
        try:
            app.state.redis.close()
        finally:
            engine.dispose()


app = FastAPI(title="Supplier-Invoice-Verification API", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready(response: Response) -> dict[str, str]:
    database_status = "ok"
    redis_status = "ok"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        database_status = "unavailable"

    try:
        app.state.redis.ping()
    except (redis.RedisError, OSError):
        redis_status = "unavailable"

    if database_status != "ok" or redis_status != "ok":
        response.status_code = 503
        return {
            "status": "not_ready",
            "database": database_status,
            "redis": redis_status,
        }

    return {"status": "ready", "database": "ok", "redis": "ok"}
