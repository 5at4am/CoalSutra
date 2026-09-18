"""Unit tests for the document classification router (route stage)."""

import pytest

from app.models.enums import SourceType
from app.services.ingestion.router import classify_document


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("digital_pdf", SourceType.digital_pdf),
        ("scanned_pdf", SourceType.scanned_pdf),
        ("sample_image", SourceType.image),
        ("sample_csv", SourceType.spreadsheet),
    ],
)
def test_classify_by_content(fixture_name, expected, request):
    path = request.getfixturevalue(fixture_name)
    assert classify_document(str(path)) is expected


def test_mime_type_hint_does_not_override_image(sample_image):
    assert (
        classify_document(str(sample_image), "application/octet-stream")
        is SourceType.image
    )


def test_scanned_pdf_is_decided_by_missing_text_layer(scanned_pdf):
    assert classify_document(str(scanned_pdf)) is SourceType.scanned_pdf


def test_unsupported_extension_raises(tmp_path):
    file = tmp_path / "notes.txt"
    file.write_text("plain notes")
    with pytest.raises(ValueError):
        classify_document(str(file))