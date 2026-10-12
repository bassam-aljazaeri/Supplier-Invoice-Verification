import os
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine


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
