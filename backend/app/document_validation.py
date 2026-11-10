"""Hash/size verification and bounded, credential-free parser subprocess."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from app.storage import StorageIntegrity

REJECTIONS = {"invalid_file", "unsupported_type", "pdf_encrypted", "pdf_page_count", "image_frame_count", "image_dimensions", "parser_limit"}


def child(argument, input_fd=None, timeout=20):
    environment = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.document_parser", str(argument), str(os.getpid())],
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
            env=environment, cwd=str(Path(__file__).resolve().parents[1]),
            close_fds=True, pass_fds=() if input_fd is None else (input_fd,), start_new_session=True,
        )
        try:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                return {"state": "rejected", "code": "parser_limit"}
            if process.returncode != 0:
                return {"state": "rejected", "code": "parser_limit"} if process.returncode < 0 else {"state": "temporary", "code": "processing_error"}
            output.seek(0)
            raw = output.read(4097)
            if len(raw) > 4096:
                raise ValueError()
            return json.loads(raw)
        finally:
            try:
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass  # Child exited between poll and signal; still reap it.
            finally:
                process.wait()


def check_containment():
    if child("probe") != {"contained": True, "credentials_absent": True}:
        raise RuntimeError("Document parser containment unavailable.")


def validate(storage, attempt):
    root = Path(os.getenv("DOCUMENT_TEMP_ROOT", "/tmp/siv-documents"))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    deadline, size, digest = time.monotonic() + 15, 0, hashlib.sha256()
    with tempfile.TemporaryFile(dir=root) as file:
        with storage.open_bounded(attempt.storage_key, 5000000) as source:
            while data := source.read(65536):
                if time.monotonic() >= deadline:
                    from app.storage import StorageUnavailable
                    raise StorageUnavailable()
                size += len(data)
                digest.update(data)
                file.write(data)
        if size != attempt.byte_size or digest.hexdigest() != attempt.sha256:
            raise StorageIntegrity()
        file.flush()
        # The child receives only a read-only anonymous input fd, never storage paths.
        descriptor = os.open(f"/proc/self/fd/{file.fileno()}", os.O_RDONLY)
        try:
            result = child(descriptor, descriptor)
        finally:
            os.close(descriptor)
    if result == {"state": "accepted", "detected_type": result.get("detected_type")} and result.get("detected_type") in {"pdf", "jpeg", "png"}:
        return result
    if result.get("state") == "rejected" and result.get("code") in REJECTIONS and len(result) == 2:
        return result
    return {"state": "temporary", "code": "processing_error"}
