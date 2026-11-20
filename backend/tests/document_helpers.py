"""Generate original fictional fixtures using only the Python standard library."""

import binascii
import struct
import zlib


BOUNDARY = b"fictional-boundary"


def pdf():
    content = b"BT /F1 12 Tf 20 100 Td (Fictional invoice - test only) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    data, offsets = bytearray(b"%PDF-1.7\n"), [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(str(number).encode() + b" 0 obj\n" + value + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n")
    return bytes(data)


def png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0\x80\x80\x80")) + chunk(b"IEND", b"")


def jpeg():
    def marker(kind, data):
        return b"\xff" + bytes([kind]) + struct.pack(">H", len(data) + 2) + data
    # One grayscale pixel: zero DCT coefficients, minimal DC/EOB Huffman tables.
    quantization = marker(0xdb, b"\0" + bytes([1]) * 64)
    frame = marker(0xc0, b"\x08\x00\x01\x00\x01\x01\x01\x11\x00")
    counts = b"\x01" + bytes(15)
    tables = marker(0xc4, b"\0" + counts + b"\0" + b"\x10" + counts + b"\0")
    scan = marker(0xda, b"\x01\x01\x00\x00\x3f\x00")
    return b"\xff\xd8" + quantization + frame + tables + scan + b"\x3f\xff\xd9"


def multipart(data=None, filename="fictional.pdf", field="file", extra_headers=b"", close=True):
    data = pdf() if data is None else data
    return b"--" + BOUNDARY + b'\r\nContent-Disposition: form-data; name="' + field.encode() + b'"; filename="' + filename.encode("utf-8") + b'"\r\nContent-Type: application/octet-stream\r\n' + extra_headers + b"\r\n" + data + (b"\r\n--" + BOUNDARY + b"--\r\n" if close else b"")


def upload_headers(key=None):
    return {"Content-Type": "multipart/form-data; boundary=" + BOUNDARY.decode(), **({"Idempotency-Key": str(key)} if key is not None else {})}
