"""Fixed Linux child entrypoint. Untrusted bytes never enter the Celery process.

Seccomp is intentionally small: deny networking/process creation before parsing.
This is resource containment, not a promise of malware detection or a full sandbox.
"""

import ctypes
import errno
import json
import logging
import os
import platform
import resource
import signal
import sys
import warnings


def contain(parent):
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4096, 4096))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0 or os.getppid() != parent:
        raise RuntimeError("containment")
    machine = platform.machine()
    if machine == "x86_64":
        arch = 0xC000003E
        denied = list(range(41, 56)) + [288, 299, 307, 56, 57, 58, 59, 322, 435, 101, 310, 311, 272, 308, 321, 298, 425, 426, 427]
    elif machine == "aarch64":
        arch = 0xC00000B7
        denied = list(range(198, 213)) + [242, 243, 269, 220, 221, 281, 435, 117, 270, 271, 97, 268, 280, 241, 425, 426, 427]
    else:
        raise RuntimeError("containment")

    class Filter(ctypes.Structure):
        _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte), ("jf", ctypes.c_ubyte), ("k", ctypes.c_uint32)]

    class Program(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.POINTER(Filter))]

    instructions = [(0x20, 0, 0, 4), (0x15, 1, 0, arch), (0x06, 0, 0, 0x80000000), (0x20, 0, 0, 0)]
    # Deny x32 syscall aliases, which otherwise bypass the x86_64 deny list.
    instructions += [(0x35, 0, 1, 0x40000000), (0x06, 0, 0, 0x00050000 | errno.EPERM)]
    for number in denied:
        instructions += [(0x15, 0, 1, number), (0x06, 0, 0, 0x00050000 | errno.EPERM)]
    instructions.append((0x06, 0, 0, 0x7FFF0000))
    filters = (Filter * len(instructions))(*(Filter(*row) for row in instructions))
    program = Program(len(instructions), filters)
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise RuntimeError("containment")


def parse(file):
    from PIL import Image, ImageFile
    from pypdf import PdfReader

    head = file.read(8)
    file.seek(0)
    if head.startswith(b"%PDF-"):
        reader = PdfReader(file, strict=True, password=None)
        if reader.is_encrypted:
            return {"state": "rejected", "code": "pdf_encrypted"}
        if len(reader.pages) != 1:
            return {"state": "rejected", "code": "pdf_page_count"}
        content = reader.pages[0].get_contents()
        if content is not None:
            _ = content.operations  # Parse content syntax; no rendering, actions or extraction.
        return {"state": "accepted", "detected_type": "pdf"}
    if not (head.startswith(b"\xff\xd8\xff") or head == b"\x89PNG\r\n\x1a\n"):
        return {"state": "rejected", "code": "unsupported_type"}
    if head == b"\x89PNG\r\n\x1a\n":
        file.seek(8)
        while chunk := file.read(8):
            if len(chunk) != 8:
                raise ValueError()
            length = int.from_bytes(chunk[:4], "big")
            if chunk[4:] == b"acTL":
                return {"state": "rejected", "code": "image_frame_count"}
            if length > 5000000:
                raise ValueError()
            file.seek(length + 4, 1)
            if chunk[4:] == b"IEND":
                break
        file.seek(0)
    Image.MAX_IMAGE_PIXELS = 10000000
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(file, formats=("JPEG", "PNG")) as image:
            if image.format == "MPO" or getattr(image, "n_frames", 1) != 1:
                return {"state": "rejected", "code": "image_frame_count"}
            width, height = image.size
            if min(width, height) <= 0 or max(width, height) > 10000 or width * height > 10000000:
                return {"state": "rejected", "code": "image_dimensions"}
            kind = {"JPEG": "jpeg", "PNG": "png"}.get(image.format)
            if kind is None:
                return {"state": "rejected", "code": "unsupported_type"}
            image.verify()
        file.seek(0)
        with Image.open(file, formats=("JPEG", "PNG")) as image:
            image.load()
    return {"state": "accepted", "detected_type": kind}


def main():
    logging.disable(logging.CRITICAL)
    # Trusted plugin imports happen before seccomp; untrusted input is not read yet.
    from PIL import Image
    from pypdf.errors import FileNotDecryptedError
    Image.init()
    result = {"state": "temporary", "code": "processing_error"}
    try:
        contain(int(sys.argv[2]))
    except Exception:
        print(json.dumps(result))
        return
    try:
        if sys.argv[1] == "probe":
            import socket
            try:
                socket.socket()
            except PermissionError:
                result = {"contained": resource.getrlimit(resource.RLIMIT_AS) == (256 * 1024**2,) * 2 and resource.getrlimit(resource.RLIMIT_CPU) == (10, 10), "credentials_absent": not any(k.startswith(("POSTGRES_", "AWS_", "COGNITO_")) for k in os.environ)}
        else:
            with os.fdopen(int(sys.argv[1]), "rb") as file:
                result = parse(file)
    except FileNotDecryptedError:
        result = {"state": "rejected", "code": "pdf_encrypted"}
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        result = {"state": "rejected", "code": "image_dimensions"}
    except MemoryError:
        result = {"state": "rejected", "code": "parser_limit"}
    except Exception:
        result = {"state": "rejected", "code": "invalid_file"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
