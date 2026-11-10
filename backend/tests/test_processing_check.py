"""Controlled checker failures; real database contention is tested separately."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from scripts import check_processing as processing


NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


class NoDatabase:
    @contextmanager
    def transaction(self):
        yield None


def poll(row):
    check = object.__new__(processing.Check)
    check.jobs = NoDatabase()
    check.observation = lambda session, label: row
    return check.publish_failed("outage")


def observation(**overrides):
    row = dict(state="queued", error_code=None, dispatch="pending", attempts=0,
               dispatch_updated_at=NOW, next_dispatch_at=NOW + timedelta(seconds=30), observed_at=NOW)
    row.update(overrides)
    return row


@pytest.mark.parametrize("row", [
    observation(dispatch="publishing"),  # Valid in flight, not evidence of failure/backoff.
    observation(next_dispatch_at=NOW),  # Initial pending upload has not been published.
    observation(next_dispatch_at=NOW - timedelta(seconds=1)),
])
def test_outage_poll_waits_for_actual_failed_publish_backoff(row):
    assert poll(row) is False


def test_outage_poll_requires_pending_future_thirty_second_backoff():
    assert poll(observation()) is True


@pytest.mark.parametrize("row,code", [
    (None, "outage_document_present"),
    (observation(dispatch=None), "outage_job_present"),
    (observation(state="processing"), "outage_document_queued"),
    (observation(error_code="processing_error"), "outage_document_queued"),
    (observation(attempts=1), "outage_no_processing_attempt"),
    (observation(dispatch="published"), "outage_dispatch_pending_or_publishing"),
    (observation(dispatch="inactive"), "outage_dispatch_pending_or_publishing"),
    (observation(next_dispatch_at=NOW + timedelta(seconds=15)), "outage_publish_backoff_30_seconds"),
])
def test_outage_poll_keeps_invariants_and_identifies_failure(row, code):
    with pytest.raises(processing.ProcessingCheckFailure) as error:
        poll(row)
    assert error.value.code == code


def test_outage_deadline_has_specific_safe_code(monkeypatch):
    ticks = iter((0, 0, 100))
    monkeypatch.setattr(processing.time, "monotonic", lambda: next(ticks))
    sleeps = []
    monkeypatch.setattr(processing.time, "sleep", sleeps.append)
    with pytest.raises(processing.ProcessingCheckFailure) as error:
        processing.wait(lambda: False, failure_code="outage_publish_backoff_deadline")
    assert error.value.code == "outage_publish_backoff_deadline"
    assert sleeps == [0.25]


@pytest.mark.parametrize("error,code,kind", [
    (processing.ProcessingCheckFailure("outage_no_processing_attempt"), "outage_no_processing_attempt", "ProcessingCheckFailure"),
    (AttributeError("fictional-secret-value"), "unexpected_exception", "AttributeError"),
    (OperationalError("SELECT 'fictional-secret-value'", {"token": "fictional-secret-value"}, Exception("fictional-secret-value")), "unexpected_exception", "OperationalError"),
])
def test_main_reports_safe_failure_identity_without_raw_exception_or_sql(monkeypatch, capsys, error, code, kind):
    closed = []
    class FailedCheck:
        storage = SimpleNamespace(close=lambda: closed.append("storage"))
        engine = SimpleNamespace(dispose=lambda: closed.append("engine"))
        def run(self, phase):
            raise error
        def diagnostics(self):
            raise RuntimeError("fictional-secret-value")
    monkeypatch.setattr(processing, "Check", FailedCheck)
    monkeypatch.setattr(processing.sys, "argv", ["check_processing", "outage-upload"])
    assert processing.main() == 1
    captured = capsys.readouterr()
    assert "fictional-secret-value" not in captured.err + captured.out
    details = json.loads(captured.err.splitlines()[1])
    assert details["check"] == code and details["exception_type"] == kind
    assert details["site"].startswith("main:")
    assert set(details) == {"check", "exception_type", "site"}
    assert closed == ["storage", "engine"]
