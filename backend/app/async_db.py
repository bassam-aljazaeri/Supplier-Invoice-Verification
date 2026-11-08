"""Keep request-owned synchronous sessions alive until their DB call has exited."""

import asyncio

from fastapi.concurrency import run_in_threadpool


async def database_call(operation, *args, **kwargs):
    work = asyncio.create_task(run_in_threadpool(operation, *args, **kwargs))
    try:
        return await asyncio.shield(work)
    except asyncio.CancelledError:
        # A thread cannot be cancelled by cancelling its awaiter. Do not race
        # session rollback/close against an in-progress commit or query.
        while not work.done():
            try:
                await asyncio.shield(work)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not work.cancelled():
            work.exception()
        raise
