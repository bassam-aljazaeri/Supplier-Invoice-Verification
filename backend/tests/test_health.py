from fastapi.testclient import TestClient

from app import main


class SuccessfulConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        assert str(statement) == "SELECT 1"


class SuccessfulEngine:
    def connect(self):
        return SuccessfulConnection()

    def dispose(self):
        pass


class SuccessfulRedis:
    def ping(self):
        return True

    def close(self):
        pass


def client(monkeypatch, *, database=None, redis_client=None):
    monkeypatch.setattr(main, "engine", database or SuccessfulEngine())
    monkeypatch.setattr(
        main,
        "create_redis_client",
        lambda: redis_client or SuccessfulRedis(),
    )
    return TestClient(main.app)


def test_health_is_independent_of_dependencies(monkeypatch):
    class UnavailableEngine:
        def connect(self):
            raise AssertionError("health must not connect to the database")

        def dispose(self):
            pass

    class UnavailableRedis:
        def ping(self):
            raise AssertionError("health must not ping Redis")

        def close(self):
            pass

    with client(
        monkeypatch,
        database=UnavailableEngine(),
        redis_client=UnavailableRedis(),
    ) as api:
        response = api.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_when_both_dependencies_succeed(monkeypatch):
    with client(monkeypatch) as api:
        response = api.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ok",
        "redis": "ok",
    }


def test_ready_reports_database_failure_without_exception_details(monkeypatch):
    class DatabaseUnavailable:
        def connect(self):
            raise OSError("private database detail")

        def dispose(self):
            pass

    with client(
        monkeypatch,
        database=DatabaseUnavailable(),
    ) as api:
        response = api.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
        "redis": "ok",
    }
    assert "private" not in response.text


def test_ready_reports_redis_failure_without_exception_details(monkeypatch):
    class RedisUnavailable:
        def ping(self):
            raise main.redis.ConnectionError("private redis detail")

        def close(self):
            pass

    with client(monkeypatch, redis_client=RedisUnavailable()) as api:
        response = api.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "ok",
        "redis": "unavailable",
    }
    assert "private" not in response.text
