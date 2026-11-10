"""Generated, fictional parser fixtures; never external or financial documents."""

from io import BytesIO

from PIL import Image
from pypdf import PdfWriter


def pdf(pages=1, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=300, height=300)
    if encrypted:
        writer.encrypt("fictional-password")
    file = BytesIO()
    writer.write(file)
    return file.getvalue()


def image(kind="PNG", size=(2, 2), animated=False):
    file = BytesIO()
    first = Image.new("RGB", size, "white")
    extra = dict(save_all=True, append_images=[Image.new("RGB", size, "black")], duration=100, loop=0) if animated else {}
    first.save(file, format=kind, **extra)
    return file.getvalue()
