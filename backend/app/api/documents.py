"""Authenticated document APIs. Uploads queue durable work, never execute it."""

import asyncio
import hashlib
import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from app.async_db import database_call as run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from app.api.dependencies import SessionDependency, UserDependency, WorkspaceDependency
from app.api.errors import BusinessError, BusinessRoute, forbidden, invalid, unavailable
from app.document_runtime import STORAGE_WAIT, storage_call, verify_object
from app.document_upload import receive_file, upload_boundary
from app.schemas.document import DocumentDownload, DocumentList, DocumentQuery, DocumentRead
from app.schemas.errors import BusinessErrorResponse
from app.services import documents as service
from app.storage import StorageError, StorageIntegrity


def read_post(endpoint):
    endpoint.document_read_permission = True
    return endpoint


class DocumentRoute(BusinessRoute):
    def requires_write(self, request):
        return request.method != "GET" and not getattr(self.endpoint, "document_read_permission", False)

    async def before_request(self, request):
        upload = self.path == "/documents" and request.method == "POST"
        keys = request.headers.getlist("idempotency-key")
        if upload:
            try:
                if len(keys) != 1:
                    raise ValueError()
                key = UUID(keys[0])
                if str(key) != keys[0]:
                    raise ValueError()
                request.state.upload_attempt_key = key
            except (ValueError, TypeError, AttributeError):
                raise invalid("idempotency_key", "Provide one canonical UUID Idempotency-Key.") from None
            request.state.upload_boundary = upload_boundary(request)
        elif keys:
            raise invalid("idempotency_key", "Idempotency-Key is allowed only for document uploads.")
        allowed = {"limit", "offset", "state", "upload_attempt_key"} if self.path == "/documents" and request.method == "GET" else {"ticket"} if self.path.endswith("/local-content") else set()
        if any(name not in allowed or len(request.query_params.getlist(name)) != 1 for name in request.query_params):
            raise invalid("request", "Use only the supported query parameters, once each.")
        if not upload:
            try:
                async for chunk in request.stream():
                    if chunk:
                        raise invalid("request", "This operation requires an empty body.")
            except ClientDisconnect:
                raise unavailable() from None

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request):
            try:
                async with asyncio.timeout(90 if self.path == "/documents" and request.method == "POST" else 5):
                    return await handler(request)
            except TimeoutError:
                return unavailable().response()
        return bounded


router = APIRouter(prefix="/documents", tags=["Private documents"], route_class=DocumentRoute)
WORKSPACE_PARAMETER = {"name": "X-Workspace-ID", "in": "header", "required": True, "schema": {"type": "string", "format": "uuid"}}
AUTH_EXTRA = {"parameters": [WORKSPACE_PARAMETER]}
UPLOAD_EXTRA = {
    "parameters": [WORKSPACE_PARAMETER, {"name": "Idempotency-Key", "in": "header", "required": True, "schema": {"type": "string", "format": "uuid"}}],
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "additionalProperties": False, "required": ["file"],
        "properties": {"file": {"type": "string", "format": "binary", "description": "One PDF/JPEG/PNG candidate, 1-5,000,000 bytes; validated structurally later."}},
    }}}},
}


def queued_response(result, status=202):
    return JSONResponse(status_code=status, content=result.model_dump(mode="json"), headers={
        "Location": f"/documents/{result.id}", **({"Retry-After": "3"} if status == 202 else {}),
    })


@router.post("", response_model=DocumentRead, status_code=202, openapi_extra=UPLOAD_EXTRA, responses={
    200: {"model": DocumentRead, "description": "Terminal upload replay."},
    413: {"model": BusinessErrorResponse, "description": "Upload exceeds file/body limits."},
    415: {"model": BusinessErrorResponse, "description": "Unsupported upload media or encoding."},
})
async def upload_document(request: Request, session: SessionDependency, user: UserDependency, workspace_id: WorkspaceDependency):
    runtime = request.app.state.documents
    if not runtime.slots.acquire(blocking=False):
        raise unavailable()
    received, writing, clone = None, None, None
    try:
        caller_id, role = user.id, request.state.membership_role
        # Do not retain the authorization read transaction while receiving bytes.
        await run_in_threadpool(session.rollback)
        received = await receive_file(request, request.state.upload_boundary, runtime.temp_dir)
        reservation = await run_in_threadpool(service.reserve_upload, session, workspace_id, caller_id, request.state.upload_attempt_key, received, role)
        storage = runtime.get_storage()
        if reservation.token is None:
            if reservation.verify_object:
                await storage_call(verify_object, storage, reservation.storage_key, received.size, received.sha256)
            return queued_response(reservation.result, 200 if reservation.result.state in service.TERMINAL else 202)
        # The writer owns a separate descriptor even if the HTTP request times out.
        clone = os.fdopen(os.dup(received.file.fileno()), "rb")

        def write_private():
            with clone:
                storage.put_new(reservation.storage_key, clone, received.size, received.sha256)

        writing = runtime.track(asyncio.create_task(asyncio.to_thread(write_private)))
        try:
            await asyncio.wait_for(asyncio.shield(writing), STORAGE_WAIT)
        except (StorageError, OSError, TimeoutError):
            raise unavailable() from None
        result = await run_in_threadpool(service.finalize_upload, session, workspace_id, reservation)
        return queued_response(result)
    except (StorageError, OSError):
        raise unavailable() from None
    finally:
        if received is not None:
            received.file.close()
        if writing is not None and not writing.done():
            # Keep the four-upload capacity bound until a late writer actually exits.
            writing.add_done_callback(lambda future: runtime.slots.release())
        else:
            if clone is not None:
                clone.close()
            runtime.slots.release()


@router.get("", response_model=DocumentList, openapi_extra=AUTH_EXTRA)
def list_documents(params: Annotated[DocumentQuery, Query()], request: Request, session: SessionDependency, user: UserDependency, workspace_id: WorkspaceDependency):
    rows, total = service.list_documents(session, workspace_id, user.id, request.state.membership_role, params)
    return DocumentList(items=rows, limit=params.limit, offset=params.offset, total=total)


@router.get("/{id}", response_model=DocumentRead, openapi_extra=AUTH_EXTRA)
def retrieve_document(id: UUID, request: Request, session: SessionDependency, workspace_id: WorkspaceDependency):
    return service.read_document(session, workspace_id, id, request.state.membership_role)


@router.post("/{id}/retry", response_model=DocumentRead, status_code=202, openapi_extra=AUTH_EXTRA)
async def retry_document(id: UUID, request: Request, session: SessionDependency, workspace_id: WorkspaceDependency):
    role = request.state.membership_role
    current = await run_in_threadpool(service.read_document, session, workspace_id, id, role)
    if not current.can_retry:
        raise BusinessError(409, "conflict", "This document is not eligible for another processing attempt.")
    key, size, digest, _ = await run_in_threadpool(service.stored_reference, session, workspace_id, id)
    await storage_call(verify_object, request.app.state.documents.get_storage(), key, size, digest)
    return queued_response(await run_in_threadpool(service.retry_document, session, workspace_id, id, role))


@router.post("/{id}/download-url", response_model=DocumentDownload, openapi_extra=AUTH_EXTRA)
@read_post
async def download_url(id: UUID, request: Request, session: SessionDependency, user: UserDependency, workspace_id: WorkspaceDependency):
    caller_id = user.id
    key, size, digest, _ = await run_in_threadpool(service.stored_reference, session, workspace_id, id, accepted=True)
    storage = request.app.state.documents.get_storage()
    await storage_call(verify_object, storage, key, size, digest)
    grant = storage.download_grant(id, workspace_id, caller_id, 60)
    return DocumentDownload(document_id=id, workspace_id=workspace_id, delivery="local_authenticated", url=grant.url, expires_at=grant.expires_at)


def read_content(storage, reference):
    key, size, digest, _ = reference
    with storage.open_bounded(key, size) as file:
        payload = file.read()
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
        raise StorageIntegrity()
    return payload


@router.get("/{id}/local-content", openapi_extra=AUTH_EXTRA, response_class=Response)
async def local_content(id: UUID, ticket: Annotated[str, Query(min_length=1, max_length=512)], request: Request, session: SessionDependency, user: UserDependency, workspace_id: WorkspaceDependency):
    caller_id = user.id
    reference = await run_in_threadpool(service.stored_reference, session, workspace_id, id, accepted=True)
    storage = request.app.state.documents.get_storage()
    if not storage.verify_ticket(ticket, id, workspace_id, caller_id):
        raise forbidden()
    payload = await storage_call(read_content, storage, reference)
    content_type, extension = {"pdf": ("application/pdf", "pdf"), "jpeg": ("image/jpeg", "jpg"), "png": ("image/png", "png")}[reference[3]]
    return Response(payload, media_type=content_type, headers={
        "Content-Disposition": f'attachment; filename="document-{id}.{extension}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
    })
