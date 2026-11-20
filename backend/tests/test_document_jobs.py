"""Real disposable PostgreSQL transactions/races, separate from broker integration."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import fcntl
import hashlib
from io import BytesIO
import os
import time
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.dispatch_documents import Dispatcher
from app.models import Document, DocumentJob
from app.services.document_jobs import Jobs
from app.services.documents import retry_document
from app.storage import StorageUnavailable
from app.storage.local import LocalDocumentStorage, new_key
from scripts.check_processing import Check
from tests.document_helpers import png

pytestmark = pytest.mark.postgres


@pytest.fixture
def setup_jobs(postgres_engine, committed_memberships):
    sessions = sessionmaker(postgres_engine, expire_on_commit=False)
    jobs = Jobs(sessions)
    ws, user = committed_memberships["workspace_id"], committed_memberships["user_ids"][0]
    def add(state="queued"):
        with jobs.transaction() as s:
            now, identity = jobs.clock(s), uuid4()
            d = Document(id=identity, workspace_id=ws, uploader_id=user, upload_attempt_key=uuid4(),
                         storage_key=new_key(ws, identity), original_filename="fictional.png", byte_size=len(png()),
                         sha256=hashlib.sha256(png()).hexdigest(), state=state)
            if state == "receiving":
                d.upload_token, d.upload_lease_until = uuid4(), now - timedelta(seconds=1)
            else:
                d.uploaded_at = now
            s.add(d)
            s.flush()
            if state == "queued":
                s.add(DocumentJob(document_id=identity, workspace_id=ws, dispatch_state="pending", next_attempt_at=now, next_dispatch_at=now))
            return identity
    try:
        yield jobs, add, ws
    finally:
        with jobs.transaction() as s:
            s.execute(delete(DocumentJob).where(DocumentJob.workspace_id == ws))
            s.execute(delete(Document).where(Document.workspace_id == ws))


def due(jobs, identity, *, expired_processing=False, expired_dispatch=False):
    with jobs.transaction() as s:
        d, j = jobs.pair(s, identity)
        now = jobs.clock(s)
        if expired_processing:
            j.processing_lease_until = now - timedelta(seconds=1)
        elif expired_dispatch and j.dispatch_state == "publishing":
            j.dispatch_lease_until = now - timedelta(seconds=1)
        else:
            j.next_dispatch_at = j.next_attempt_at = now - timedelta(seconds=1)


def test_two_independent_claims_have_one_owner_and_stale_completion_is_fenced(setup_jobs):
    jobs, add, _ = setup_jobs
    identity = add()
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(jobs.claim, [identity, identity]))
    first, = [a for a in results if a]
    assert jobs.claim(identity) is None
    assert not jobs.complete(replace(first, token=uuid4()), "accepted", detected_type="png")
    due(jobs, identity, expired_processing=True)
    assert not jobs.complete(first, "accepted", detected_type="png")
    assert jobs.recover_processing(identity)
    due(jobs, identity)
    second = jobs.claim(identity)
    assert second.token != first.token
    assert not jobs.complete(first, "failed", "storage_integrity")
    assert jobs.complete(second, "accepted", detected_type="png")
    assert not jobs.complete(first, "rejected", "invalid_file")
    with jobs.transaction() as s:
        assert s.get(Document, identity).state == "accepted"
        assert s.get(DocumentJob, identity).attempt_count == 2


def test_dispatch_commit_publish_windows_and_loss(setup_jobs):
    jobs, add, _ = setup_jobs
    identity = add()
    token = jobs.claim_dispatch(identity)
    assert token and jobs.claim_dispatch(identity) is None
    due(jobs, identity, expired_dispatch=True)
    replacement = jobs.claim_dispatch(identity)
    assert replacement != token and not jobs.finish_dispatch(identity, token, True)
    assert jobs.finish_dispatch(identity, replacement, False)
    with jobs.transaction() as s:
        j = s.get(DocumentJob, identity)
        assert 28 < (j.next_dispatch_at - jobs.clock(s)).total_seconds() <= 30
        assert j.attempt_count == 0
    due(jobs, identity)
    token = jobs.claim_dispatch(identity)
    assert jobs.finish_dispatch(identity, token, True)
    with jobs.transaction() as s:
        j = s.get(DocumentJob, identity)
        assert 178 < (j.next_dispatch_at - jobs.clock(s)).total_seconds() <= 180
    assert jobs.claim_dispatch(identity) is None
    due(jobs, identity)  # Simulate lost published message becoming due.
    assert identity in jobs.candidates("dispatch")
    token = jobs.claim_dispatch(identity)
    claim = jobs.claim(identity)  # Consumer can win before producer bookkeeping.
    assert not jobs.finish_dispatch(identity, token, True)
    assert jobs.complete(claim, "accepted", detected_type="png")


@pytest.mark.parametrize("code", ["storage_unavailable", "processing_error", "processing_interrupted"])
def test_retry_delays_six_lifetime_claims_and_one_explicit_retry(setup_jobs, code):
    jobs, add, ws = setup_jobs
    identity = add()
    for count in range(1, 7):
        if count == 4:
            with jobs.transaction() as s:
                s.get(Document, identity).finished_at = jobs.clock(s) - timedelta(seconds=61)
            with jobs.sessions() as s:
                retry_document(s, ws, identity, "accountant")
        due(jobs, identity)
        attempt = jobs.claim(identity)
        with jobs.transaction() as s:
            j = s.get(DocumentJob, identity)
            assert j.attempt_count == count
            assert 118 < (j.processing_lease_until - jobs.clock(s)).total_seconds() <= 120
        assert jobs.complete(attempt, "temporary", code)
        with jobs.transaction() as s:
            d, j = s.get(Document, identity), s.get(DocumentJob, identity)
            if count % 3:
                assert d.state == "queued" and d.error_code is None
                assert (10 if count % 3 == 1 else 30) - 2 < (j.next_attempt_at - jobs.clock(s)).total_seconds() <= (10 if count % 3 == 1 else 30)
            else:
                assert d.state == "failed" and d.error_code == code
                assert j.dispatch_state == "inactive" and j.attempt_token is None
        assert jobs.claim(identity) is None


@pytest.mark.parametrize("state,code", [("rejected", "invalid_file"), ("rejected", "parser_limit"), ("failed", "storage_integrity")])
def test_permanent_outcomes_never_dispatch_again(setup_jobs, state, code):
    jobs, add, _ = setup_jobs
    identity = add()
    assert jobs.complete(jobs.claim(identity), state, code)
    assert jobs.claim(identity) is None and jobs.claim_dispatch(identity) is None


def test_expired_last_attempt_becomes_failed(setup_jobs):
    jobs, add, _ = setup_jobs
    identity = add()
    for _ in range(3):
        due(jobs, identity)
        jobs.claim(identity)
        due(jobs, identity, expired_processing=True)
        assert jobs.recover_processing(identity)
    with jobs.transaction() as s:
        assert s.get(Document, identity).error_code == "processing_interrupted"
        assert s.get(DocumentJob, identity).attempt_count == 3


@pytest.mark.parametrize("stored,outcome", [(True, "queued"), (False, "failed")])
def test_abandoned_upload_recovers_and_fences_old_writer(setup_jobs, tmp_path, stored, outcome):
    jobs, add, _ = setup_jobs
    identity = add("receiving")
    storage = LocalDocumentStorage(tmp_path)
    with jobs.transaction() as s:
        d = s.get(Document, identity)
        old = d.upload_token
        if stored:
            storage.put_new(d.storage_key, BytesIO(png()), d.byte_size, d.sha256)
    Dispatcher(jobs, storage, publisher=lambda _: False).step()
    with jobs.transaction() as s:
        d = s.get(Document, identity)
        assert d.state == outcome and d.upload_token is None
        assert (s.get(DocumentJob, identity) is not None) == stored
        from app.services.document_jobs import Attempt
        stale = Attempt(identity, d.workspace_id, d.storage_key, d.byte_size, d.sha256, old)
    assert not jobs.finish_upload(stale, "ready")
    storage.close()


def test_cleanup_keeps_live_and_completed_uploads_and_locked_partial(setup_jobs, tmp_path):
    jobs, add, _ = setup_jobs
    storage = LocalDocumentStorage(tmp_path)
    keys = []
    for state in ("receiving", "queued"):
        identity = add(state)
        with jobs.transaction() as s:
            d = s.get(Document, identity)
            if state == "receiving":
                d.upload_lease_until = jobs.clock(s) + timedelta(seconds=120)
            key = d.storage_key
            keys.append(key)
            storage.put_new(key, BytesIO(png()), d.byte_size, d.sha256)
    orphan = new_key(uuid4(), uuid4())
    storage.put_new(orphan, BytesIO(png()), len(png()), hashlib.sha256(png()).hexdigest())
    for key in [*keys, orphan]:
        os.utime(tmp_path / "objects" / key, (time.time()-90000,) * 2)
    partial = tmp_path / "partials" / (uuid4().hex + ".part")
    with partial.open("wb") as active:
        fcntl.flock(active, fcntl.LOCK_EX)
        os.utime(partial, (time.time()-90000,) * 2)
        Dispatcher(jobs, storage, publisher=lambda _: False).step()
        assert partial.exists()
        assert all((tmp_path / "objects" / key).exists() for key in keys)
        assert not (tmp_path / "objects" / orphan).exists()
    Dispatcher(jobs, storage, publisher=lambda _: False).step()
    assert not partial.exists()
    storage.close()


def test_s3_recovery_worker_and_disabled_cleanup_preserve_active_and_finalized_bytes(setup_jobs, tmp_path, monkeypatch):
    from app.document_tasks import process_document
    from app.storage.s3 import S3DocumentStorage
    from tests.s3_helpers import BUCKET, REGION, PREFIX, FakeS3
    jobs, add, _ = setup_jobs
    monkeypatch.setenv("DOCUMENT_TEMP_ROOT", str(tmp_path))
    fake = FakeS3()
    storage = S3DocumentStorage(BUCKET, REGION, PREFIX, client=fake)
    recovering, active, finalized = add("receiving"), add("receiving"), add()
    for identity in (recovering, active, finalized):
        with jobs.transaction() as s:
            d = s.get(Document, identity)
            storage.put_new(d.storage_key, BytesIO(png()), d.byte_size, d.sha256)
            if identity == active:
                d.upload_lease_until = jobs.clock(s) + timedelta(seconds=120)
    original = dict(fake.objects)
    Dispatcher(jobs, storage, publisher=lambda _: False).step()
    with jobs.transaction() as s:
        assert s.get(Document, recovering).state == "queued"
        assert s.get(DocumentJob, recovering) is not None
        assert s.get(Document, active).state == "receiving"
    process_document(recovering, jobs=jobs, storage=storage)
    process_document(finalized, jobs=jobs, storage=storage)
    with jobs.transaction() as s:
        assert s.get(Document, recovering).state == s.get(Document, finalized).state == "accepted"
    # Even unreferenced and late-published objects are retained remotely.
    orphan = new_key(uuid4(), uuid4())
    storage.put_new(orphan, BytesIO(png()), len(png()), hashlib.sha256(png()).hexdigest())
    original[PREFIX + orphan] = png()
    Dispatcher(jobs, storage, publisher=lambda _: False).step()
    assert fake.objects == original
    assert set(fake.calls) <= {"get", "put"}


@pytest.mark.parametrize("result,aged,expected,code", [
    ("integrity", False, "failed", "storage_integrity"),
    ("unavailable", False, "receiving", None),
    ("unavailable", True, "failed", "upload_incomplete"),
])
def test_receiving_outage_deadline_and_integrity(setup_jobs, result, aged, expected, code):
    jobs, add, _ = setup_jobs
    identity = add("receiving")
    if aged:
        with jobs.transaction() as s:
            s.get(Document, identity).created_at = jobs.clock(s) - timedelta(minutes=16)
    first = jobs.claim_upload(identity)
    assert first is not None and jobs.claim_upload(identity) is None
    jobs.finish_upload(first, result)
    with jobs.transaction() as s:
        d = s.get(Document, identity)
        assert (d.state, d.error_code) == (expected, code)
        assert s.get(DocumentJob, identity) is None


def test_publishing_has_no_open_transaction_and_db_failure_disables_cleanup(setup_jobs, tmp_path):
    jobs, add, _ = setup_jobs
    identity = add()
    storage = LocalDocumentStorage(tmp_path)
    def publisher(identity):
        with jobs.transaction() as s:
            d, j = jobs.pair(s, identity)
            assert d is not None and j.dispatch_state == "publishing"
        return False
    Dispatcher(jobs, storage, publisher).step()
    orphan = new_key(uuid4(), uuid4())
    storage.put_new(orphan, BytesIO(png()), len(png()), hashlib.sha256(png()).hexdigest())
    path = tmp_path / "objects" / orphan
    os.utime(path, (time.time() - 90000,) * 2)
    class UnavailableJobs:
        def candidates(self, kind):
            raise OperationalError("", {}, Exception("fictional"))
    with pytest.raises(OperationalError):
        Dispatcher(UnavailableJobs(), storage, publisher).step()
    assert path.exists()
    storage.close()


def test_simultaneous_completion_commits_once(setup_jobs):
    jobs, add, _ = setup_jobs
    identity = add()
    attempt = jobs.claim(identity)
    with ThreadPoolExecutor(2) as executor:
        outcomes = list(executor.map(lambda _: jobs.complete(attempt, "accepted", detected_type="png"), range(2)))
    assert sorted(outcomes) == [False, True]


@pytest.mark.parametrize("operation", ["claim", "complete"])
def test_worker_waits_for_brief_bookkeeping_locks_instead_of_acknowledging_unclaimed_work(setup_jobs, operation):
    jobs, add, _ = setup_jobs
    identity = add()
    attempt = jobs.claim(identity) if operation == "complete" else None
    with ThreadPoolExecutor(1) as executor:
        with jobs.transaction() as s:
            d, j = jobs.pair(s, identity)
            assert d is not None and j is not None
            future = executor.submit(jobs.claim, identity) if operation == "claim" else executor.submit(jobs.complete, attempt, "accepted", detected_type="png")
            time.sleep(0.1)
            assert not future.done()  # Independent PostgreSQL connection waits for the lock.
        result = future.result(timeout=5)
    assert result is not None if operation == "claim" else result is True


def processing_check(jobs, identity):
    # Use only records from the guarded disposable fixture, without HTTP/test keys.
    check = object.__new__(Check)
    check.jobs, check.saved = jobs, {"outage": str(identity)}
    return check


@pytest.mark.parametrize("locked", ["document", "job"])
def test_outage_poll_reads_committed_state_while_publisher_holds_row_lock(setup_jobs, locked):
    jobs, add, _ = setup_jobs
    identity = add()
    token = jobs.claim_dispatch(identity)
    check = processing_check(jobs, identity)
    with jobs.transaction() as owner:
        model = Document if locked == "document" else DocumentJob
        column = model.id if locked == "document" else model.document_id
        assert owner.scalar(select(model).where(column == identity).with_for_update()) is not None
        # Independent connection: the original SKIP LOCKED poll dereferenced None.
        # Publishing is a valid observation, but is never accepted as failed-publish proof.
        assert check.publish_failed("outage") is False
    assert jobs.finish_dispatch(identity, token, False)
    assert check.publish_failed("outage") is True


def test_outage_observer_transaction_does_not_block_publisher_bookkeeping(setup_jobs):
    jobs, add, _ = setup_jobs
    identity = add()
    token = jobs.claim_dispatch(identity)
    check = processing_check(jobs, identity)
    with jobs.transaction() as observer:
        assert check.observation(observer, "outage")["dispatch"] == "publishing"
        # Observer remains open while the independent publisher commits its failure.
        assert jobs.finish_dispatch(identity, token, False)
        assert check.observation(observer, "outage")["dispatch"] == "pending"
    assert check.publish_failed("outage") is True


def test_processing_diagnostics_do_not_take_document_or_job_row_locks(setup_jobs, capsys):
    jobs, add, _ = setup_jobs
    identity = add()
    token = jobs.claim_dispatch(identity)
    check = processing_check(jobs, identity)
    with jobs.transaction() as owner:
        d, j = jobs.pair(owner, identity)
        assert d is not None and j is not None
        check.diagnostics()
    import json
    assert json.loads(capsys.readouterr().err) == {
        "fixture": "outage", "state": "queued", "error_code": None,
        "dispatch": "publishing", "attempts": 0,
    }
    assert jobs.finish_dispatch(identity, token, False)
