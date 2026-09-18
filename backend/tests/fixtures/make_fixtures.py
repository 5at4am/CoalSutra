"""Generate synthetic sample fixtures for ingestion tests.

The fixtures are small, dependency-generated files under `tests/fixtures/` so
tests never depend on real CIL data. Re-run this module to regenerate:

    python -m tests.fixtures.make_fixtures
"""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from PIL import Image, ImageDraw
from pypdf import PdfWriter

FIXTURES_DIR = Path(__file__).resolve().parent


def create_digital_pdf(path: Path) -> Path:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=11)
    pdf.multi_cell(w=pdf.epw, h=6, text="Total reserve estimate of 1,240 MT for the Bhubaneshwari block.")
    pdf.multi_cell(w=pdf.epw, h=6, text="Overburden ratio reported at 2.1 in the Q3 survey.")
    pdf.output(str(path))
    return path


def create_scanned_pdf(path: Path) -> Path:
    writer = PdfWriter()
    for _ in range(2):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as fh:
        writer.write(fh)
    return path


def create_image(path: Path) -> Path:
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((10, 10, 490, 190), outline="black")
    draw.text((90, 90), "Reserve estimate 1,240 MT", fill="black")
    img.save(path, format="PNG")
    return path


def create_csv(path: Path) -> Path:
    path.write_text(
        "block,reserve_mt,ratio_year\n"
        "Bhubaneshwari,1240,2019\n"
        "Kusunda,938,2019\n",
        encoding="utf-8",
    )
    return path


def make_all(fixtures_dir: Path = FIXTURES_DIR) -> dict[str, Path]:
    return {
        "digital_pdf": create_digital_pdf(fixtures_dir / "digital_sample.pdf"),
        "scanned_pdf": create_scanned_pdf(fixtures_dir / "scanned_sample.pdf"),
        "sample_image": create_image(fixtures_dir / "sample_image.png"),
        "sample_csv": create_csv(fixtures_dir / "sample.csv"),
    }


if __name__ == "__main__":
    for name, path in make_all().items():
        print(f"{name} -> {path}")