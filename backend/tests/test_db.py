import pytest

from app import db


class RecordingSession:
    def __init__(self, *, rollback_fails=False):
        self.events = []
        self.rollback_fails = rollback_fails

    def rollback(self):
        self.events.append("rollback")
        if self.rollback_fails:
            raise OSError("rollback unavailable")

    def close(self):
        self.events.append("close")


def test_url_preserves_special_password_characters_without_interpolation():
    password = "synthetic:@/%?#password"
    url = db.database_url({
        "POSTGRES_USER": "test-user", "POSTGRES_PASSWORD": password,
        "POSTGRES_HOST": "db", "POSTGRES_PORT": "5432", "POSTGRES_DB": "test-db",
    })
    assert url.password == password
    assert url.drivername == "postgresql+psycopg"
    assert password not in str(url)


def test_engine_uses_bounded_connections_and_session_factory(monkeypatch):
    captured = {}

    def fake_engine(url, **options):
        captured.update(options)
        captured["url"] = url
        return "test-engine"

    monkeypatch.setattr(db, "create_engine", fake_engine)
    assert db.create_database_engine() == "test-engine"
    assert captured["connect_args"] == {"connect_timeout": 2}
    assert captured["pool_timeout"] == 3
    assert captured["pool_pre_ping"] is True
    assert captured["hide_parameters"] is True
    assert db.SessionLocal.kw["bind"] is db.engine


def test_request_session_closes_without_implicit_commit(monkeypatch):
    session = RecordingSession()
    monkeypatch.setattr(db, "SessionLocal", lambda: session)
    dependency = db.get_session()
    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)
    assert session.events == ["close"]


def test_request_session_rolls_back_and_closes_on_failure(monkeypatch):
    session = RecordingSession()
    monkeypatch.setattr(db, "SessionLocal", lambda: session)
    dependency = db.get_session()
    next(dependency)
    with pytest.raises(ValueError, match="request failed"):
        dependency.throw(ValueError("request failed"))
    assert session.events == ["rollback", "close"]


def test_request_session_closes_even_if_rollback_fails(monkeypatch):
    session = RecordingSession(rollback_fails=True)
    monkeypatch.setattr(db, "SessionLocal", lambda: session)
    dependency = db.get_session()
    next(dependency)
    with pytest.raises(OSError, match="rollback unavailable"):
        dependency.throw(ValueError("request failed"))
    assert session.events == ["rollback", "close"]


def test_cancelled_session_rolls_back_and_closes(monkeypatch):
    session = RecordingSession()
    monkeypatch.setattr(db, "SessionLocal", lambda: session)
    dependency = db.get_session()
    next(dependency)
    dependency.close()
    assert session.events == ["rollback", "close"]
