"""Bounded streaming multipart receipt; structural document parsing is Step 5.4."""

import asyncio
from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import re
import tempfile
import unicodedata

from python_multipart import MultipartParser
from python_multipart.exceptions import MultipartParseError
from python_multipart.multipart import parse_options_header
from starlette.requests import ClientDisconnect

from app.api.errors import BusinessError, invalid, unavailable
from app.storage.local import CHUNK_SIZE, MAX_FILE_SIZE

MAX_BODY_SIZE = MAX_FILE_SIZE + 65536
RECEIVE_TIMEOUT = 60
IDLE_TIMEOUT = 10
QUIET_LOGGER = logging.Logger("document_multipart_disabled")
QUIET_LOGGER.disabled = True


def too_large():
    return BusinessError(413, "validation_error", "The upload exceeds the allowed size.", [{"field": "file", "message": "Choose a file of at most 5,000,000 bytes."}])


def unsupported():
    return BusinessError(415, "validation_error", "This upload format is not supported.", [{"field": "file", "message": "Upload one PDF, JPEG, or PNG using multipart/form-data."}])


def upload_boundary(request):
    types = request.headers.getlist("content-type")
    if request.headers.getlist("content-encoding") or len(types) != 1 or len(types[0]) > 1024:
        raise unsupported()
    try:
        kind, options = parse_options_header(types[0])
        boundary = options.get(b"boundary", b"")
        if kind.lower() != b"multipart/form-data":
            raise unsupported()
        if re.fullmatch(rb"[0-9A-Za-z'()+_,./:=? \-]{1,70}", boundary) is None or boundary.endswith(b" "):
            raise invalid("file", "Submit a valid multipart boundary.")
    except (ValueError, UnicodeError):
        raise invalid("file", "Submit valid multipart headers.") from None
    lengths = request.headers.getlist("content-length")
    if lengths:
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit() or len(lengths[0]) > 20:
            raise invalid("file", "Submit a valid request length.")
        if int(lengths[0]) > MAX_BODY_SIZE:
            raise too_large()
    return boundary


@dataclass
class ReceivedFile:
    file: object
    filename: str
    size: int
    sha256: str


class MultipartReceipt:
    def __init__(self, boundary, file):
        self.file, self.size, self.parts, self.header_bytes = file, 0, 0, 0
        self.headers, self.name, self.value = {}, bytearray(), bytearray()
        self.filename, self.ended, self.part_ended = None, False, False
        self.in_headers, self.wire_header_bytes = False, 0
        self.digest = hashlib.sha256()
        callbacks = {"on_" + name: getattr(self, name) for name in (
            "part_begin", "header_field", "header_value", "header_end", "headers_finished", "part_data", "part_end", "end",
        )}
        self.parser = MultipartParser(boundary, callbacks)
        self.parser.logger = QUIET_LOGGER

    def part_begin(self):
        self.parts += 1
        if self.parts != 1:
            raise invalid("file", "Submit exactly one file and no other fields.")
        self.in_headers = True

    def _header_data(self, target, data, start, end):
        self.header_bytes += end - start
        if self.header_bytes > 8192:
            raise invalid("file", "Multipart headers exceed the allowed bounds.")
        target.extend(data[start:end])

    def header_field(self, data, start, end):
        self._header_data(self.name, data, start, end)

    def header_value(self, data, start, end):
        self._header_data(self.value, data, start, end)

    def header_end(self):
        name = bytes(self.name).lower()
        if name in self.headers or len(self.headers) >= 16:
            raise invalid("file", "Multipart headers exceed the allowed bounds.")
        self.headers[name] = bytes(self.value)
        self.name.clear()
        self.value.clear()

    def headers_finished(self):
        self.in_headers = False
        try:
            kind, options = parse_options_header(self.headers.get(b"content-disposition", b""))
            if kind.lower() != b"form-data" or options.get(b"name") != b"file" or b"filename" not in options or b"content-transfer-encoding" in self.headers:
                raise ValueError()
            filename = options[b"filename"].decode("utf-8").replace("\\", "/").rsplit("/", 1)[-1]
            if not 1 <= len(filename) <= 255 or not filename.strip() or filename in {".", ".."} or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in filename):
                raise ValueError()
            self.filename = filename
        except (ValueError, UnicodeError):
            raise invalid("file", "Submit one file with a valid display filename.") from None

    def part_data(self, data, start, end):
        self.size += end - start
        if self.size > MAX_FILE_SIZE:
            raise too_large()
        chunk = data[start:end]
        self.digest.update(chunk)
        self.file.write(chunk)

    def part_end(self):
        self.part_ended = True

    def end(self):
        self.ended = True


async def receive_file(request, boundary, temp_root):
    file = None
    try:
        root = Path(temp_root)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not root.is_absolute() or root.resolve() != root:
            raise OSError()
        root.chmod(0o700)
        file = tempfile.TemporaryFile(dir=root)
        receipt = MultipartReceipt(boundary, file)
        received, fed = 0, 0
        stream = request.stream().__aiter__()
        async with asyncio.timeout(RECEIVE_TIMEOUT):
            while True:
                try:
                    chunk = await asyncio.wait_for(anext(stream), IDLE_TIMEOUT)
                except StopAsyncIteration:
                    break
                received += len(chunk)
                if received > MAX_BODY_SIZE:
                    raise too_large()
                offset = 0
                while offset < len(chunk):
                    # Header whitespace/punctuation also counts, even if the parser
                    # omits it from header callbacks. Header parsing is at most 8 KiB.
                    step = 1 if receipt.parts == 0 or receipt.in_headers else CHUNK_SIZE
                    part = chunk[offset:offset + step]
                    offset += len(part)
                    fed += len(part)
                    was_headers = receipt.in_headers
                    receipt.parser.write(part)
                    if was_headers or receipt.in_headers:
                        receipt.wire_header_bytes += len(part)
                        if receipt.wire_header_bytes > 8192:
                            raise invalid("file", "Multipart headers exceed the allowed bounds.")
                    if fed - receipt.size > 65536:
                        raise too_large()
        receipt.parser.finalize()
        # finalize() alone does not establish a complete closing boundary.
        if receipt.parts != 1 or not receipt.ended or not receipt.part_ended or receipt.filename is None or receipt.size == 0:
            raise invalid("file", "Submit one complete, nonempty multipart file.")
        file.seek(0)
        prefix = file.read(16)
        if not (re.match(rb"%PDF-[12]\.[0-9]", prefix) or prefix.startswith(b"\xff\xd8\xff") or prefix.startswith(b"\x89PNG\r\n\x1a\n")):
            raise unsupported()
        file.seek(0)
        return ReceivedFile(file, receipt.filename, receipt.size, receipt.digest.hexdigest())
    except (TimeoutError, ClientDisconnect, OSError):
        if file is not None:
            file.close()
        raise unavailable() from None
    except MultipartParseError:
        if file is not None:
            file.close()
        raise invalid("file", "Submit valid multipart data.") from None
    except BaseException:
        if file is not None:
            file.close()
        raise
