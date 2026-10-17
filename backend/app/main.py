import os
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import engine
from app.auth import AccessTokenVerifier
from app.cognito import access_token_settings
from app.api import delivery_receipts, invoices, me, memberships, purchase_orders, suppliers, workspaces


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
    if app.state.token_verifier is None:
        app.state.token_verifier = AccessTokenVerifier(access_token_settings())
    app.state.redis = create_redis_client()
    try:
        yield
    finally:
        try:
            app.state.redis.close()
        finally:
            engine.dispose()


def health() -> dict[str, str]:
    return {"status": "ok"}


def ready(response: Response, request: Request) -> dict[str, str]:
    database_status = "ok"
    redis_status = "ok"

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        database_status = "unavailable"

    try:
        request.app.state.redis.ping()
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


def create_app(*, verifier: AccessTokenVerifier | None = None) -> FastAPI:
    application = FastAPI(title="Supplier-Invoice-Verification API", lifespan=lifespan)
    application.state.token_verifier = verifier
    for router in (suppliers.router, purchase_orders.router, delivery_receipts.router, invoices.router, me.router, workspaces.router, memberships.router):
        application.include_router(router)
    application.add_api_route("/health", health, methods=["GET"])
    application.add_api_route("/ready", ready, methods=["GET"])
    return application


app = create_app()
