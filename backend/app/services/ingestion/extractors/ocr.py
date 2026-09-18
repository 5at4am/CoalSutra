"""OCR-based text extraction for `scanned_pdf` and `image` documents.

Providers (swap via `OCR_PROVIDER`):
- `tesseract` (default): pytesseract + pdf2image. Needs the tesseract binary and
  poppler installed on the machine (both are present in the backend Docker image).
- `rapidocr`: RapidOCR (ONNX) + PyMuPDF. Pure-pip, no system binaries — used on
  dev machines (e.g. Windows) where tesseract/poppler are unavailable.
- `huggingface`: hosted image-to-text OCR via the Hugging Face Inference API
  (set `HUGGINGFACE_API_KEY` + `OCR_HF_MODEL`). PDFs are rasterized with
  PyMuPDF client-side, then each page is OCR'd server-side.

If the configured provider is not usable at runtime (missing binary / network
or endpoint error), extraction auto-falls back to `rapidocr` so ingestion never
silently dies. A Vision-LLM provider can be added later behind the same
`OCRProvider` protocol.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
)


class OCRProvider(Protocol):
    def extract(self, file_path: str) -> list[dict[str, Any]]: ...


def _is_missing_binary_error(exc: Exception) -> bool:
    """True when an OCR failure is caused by a missing system binary, so the
    caller can safely swap to another provider instead of surfacing the error."""
    return isinstance(exc, FileNotFoundError) or type(exc).__name__ in {
        "TesseractNotFoundError",
        "PDFInfoNotInstalledError",
    }


class TesseractOCRProvider:
    def __init__(self, lang: str = "eng", dpi: int = 150):
        self.lang = lang
        self.dpi = dpi

    def extract(self, file_path: str) -> list[dict[str, Any]]:
        import pytesseract

        path = Path(file_path)
        if path.suffix.lower() in IMAGE_SUFFIXES:
            text = pytesseract.image_to_string(str(path), lang=self.lang)
            return [{"page_number": 1, "text": text.strip()}]

        from pdf2image import convert_from_path

        images = convert_from_path(str(path), dpi=self.dpi)
        pages: list[dict[str, Any]] = []
        for number, image in enumerate(images, start=1):
            text = pytesseract.image_to_string(image, lang=self.lang)
            pages.append({"page_number": number, "text": text.strip()})
        return pages


class RapidOCROCRProvider:
    """RapidOCR (ONNX) for pixels + PyMuPDF for PDF->image rendering.

    Works with zero system binaries, so it is the reliable local-dev OCR path.
    The ONNX engine is constructed lazily (first call is ~1-3 s/page) so the
    module imports cleanly even where rapidocr is not installed.
    """

    def __init__(self, dpi: int = 200):
        self.dpi = dpi
        self._engine: Any | None = None

    def _get_engine(self) -> Any:
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def extract(self, file_path: str) -> list[dict[str, Any]]:
        import pymupdf

        path = Path(file_path)
        if path.suffix.lower() in IMAGE_SUFFIXES:
            return [{"page_number": 1, "text": self._ocr_image(str(path))}]

        pages: list[dict[str, Any]] = []
        doc = pymupdf.open(str(path))
        try:
            for number, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=self.dpi)
                render_path = path.with_name(f"{path.name}.p{number}.png")
                try:
                    pix.save(str(render_path))
                    pages.append(
                        {"page_number": number, "text": self._ocr_image(str(render_path))}
                    )
                finally:
                    render_path.unlink(missing_ok=True)
        finally:
            doc.close()
        return pages

    def _ocr_image(self, image_path: str) -> str:
        result = self._get_engine()(image_path)
        if not result or not result[0]:
            return ""
        items: list[tuple[float, float, str]] = []
        for raw in result[0]:
            if not isinstance(raw, (list, tuple)) or not raw:
                continue
            box, text = raw[0], raw[1]
            if not isinstance(box, (list, tuple)) or len(box) < 3:
                continue
            try:
                y_min = min(pt[1] for pt in box)
                y_max = max(pt[1] for pt in box)
                x_min = min(pt[0] for pt in box)
            except (TypeError, KeyError):
                continue
            conf = raw[2] if len(raw) >= 3 else 0.0
            try:
                if float(conf) < 0.35:
                    continue
            except (TypeError, ValueError):
                pass
            text = str(text).strip()
            if text:
                items.append((x_min, (y_min + y_max) / 2.0, (y_max - y_min), text))
        if not items:
            return ""
        items.sort(key=lambda it: (it[1], it[0]))
        # Group words/lines that sit on the same visual baseline (OCR splits
        # table cells into separate boxes; rejoin them into proper rows so the
        # downstream normalizer sees "March 1988 2,840 24 118.3" not 4 fragments).
        lines: list[str] = []
        current_y: float | None = None
        current_tol: float = 0.0
        current: list[str] | None = None
        for x_min, y_center, height, text in items:
            y = y_center
            if current is None:
                current_y, current_tol = y, max(6.0, height * 0.6)
                current = [text]
                continue
            if abs(y - current_y) <= current_tol:
                current.append(text)
            else:
                lines.append(" ".join(current))
                current_y, current_tol = y, max(6.0, height * 0.6)
                current = [text]
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines)


class HuggingFaceOCRProvider:
    """Hosted image-to-text OCR via the Hugging Face Inference API.

    Files (images or PDFs rasterized to images client-side) are POSTed to
    POST https://api-inference.huggingface.co/models/{model}. The API returns
    ``[{"generated_text": "..."}]`` for image-to-text tasks.
    """

    INFERENCE_URL = "https://api-inference.huggingface.co/models/{model}"

    def __init__(self, model: str | None = None, timeout: float = 120.0):
        self.model = (model or settings.OCR_HF_MODEL).strip()
        self.timeout = timeout

    def extract(self, file_path: str) -> list[dict[str, Any]]:
        path = Path(file_path)
        if path.suffix.lower() in IMAGE_SUFFIXES:
            return [{"page_number": 1, "text": self._ocr_image(path)}]

        import pymupdf

        pages: list[dict[str, Any]] = []
        doc = pymupdf.open(str(path))
        try:
            for number, page in enumerate(doc, start=1):
                pix = page.get_pixmap(dpi=200)
                render_path = path.with_name(f"{path.name}.p{number}.png")
                try:
                    pix.save(str(render_path))
                    pages.append(
                        {"page_number": number, "text": self._ocr_image(render_path)}
                    )
                finally:
                    render_path.unlink(missing_ok=True)
        finally:
            doc.close()
        return pages

    def _ocr_image(self, image_path: Path) -> str:
        import httpx

        if not settings.HUGGINGFACE_API_KEY:
            raise RuntimeError(
                "HuggingFaceOCRProvider: HUGGINGFACE_API_KEY is not configured"
            )
        headers = {"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"}
        url = self.INFERENCE_URL.format(model=self.model)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                url, headers=headers, content=image_path.read_bytes()
            )
            response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            texts = [
                str(item["generated_text"]).strip()
                for item in data
                if isinstance(item, dict) and item.get("generated_text")
            ]
            return "\n".join(texts)
        return ""


def get_ocr_provider(name: str | None = None) -> OCRProvider:
    provider = (name or settings.OCR_PROVIDER or "tesseract").lower()
    if provider == "vision_llm":
        raise NotImplementedError("Vision-LLM OCR provider not implemented yet")
    if provider == "rapidocr":
        return RapidOCROCRProvider()
    if provider in {"huggingface", "hf_ocr", "hf"}:
        return HuggingFaceOCRProvider()
    if provider in {"tesseract", "paddleocr"}:
        return TesseractOCRProvider()
    raise ValueError(f"Unknown OCR provider: {provider}")


def extract(file_path: str) -> list[dict[str, Any]]:
    provider = get_ocr_provider()
    try:
        return provider.extract(file_path)
    except Exception as exc:  # noqa: BLE001
        fallback_ok = isinstance(provider, HuggingFaceOCRProvider) or _is_missing_binary_error(exc)
        if fallback_ok and not isinstance(provider, RapidOCROCRProvider):
            logger.warning(
                "OCR provider %s failed (%s: %s) - falling back to rapidocr",
                settings.OCR_PROVIDER or "tesseract",
                type(exc).__name__,
                exc,
            )
            return get_ocr_provider("rapidocr").extract(file_path)
        raise