"""Cancellation must not close a session while its synchronous operation runs."""

import asyncio
from threading import Event

import pytest

from app.async_db import database_call


@pytest.mark.parametrize("failure", [False, True])
def test_cancellation_waits_for_worker_before_request_cleanup(failure):
    async def exercise():
        loop, entered, release, events = asyncio.get_running_loop(), asyncio.Event(), Event(), []
        def operation():
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5)
            events.append("db-exited")
            if failure:
                raise RuntimeError("fictional private diagnostic")
        async def request():
            try:
                await database_call(operation)
            finally:
                events.append("session-closed")
        task = asyncio.create_task(request())
        try:
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            await asyncio.sleep(0)
            assert events == []
            task.cancel()  # Repeated cancellation must preserve the same ordering.
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert events == ["db-exited", "session-closed"]
    asyncio.run(exercise())
