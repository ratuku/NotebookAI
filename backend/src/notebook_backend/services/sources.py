import warnings
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

MAX_TEXT = 200_000


def text_segments(text: str) -> list[dict]:
    # Bound each citation; splitting long paragraphs also makes retrieval more useful.
    segments = []
    for paragraph, value in enumerate(text.splitlines(), 1):
        for start in range(0, len(value), 1000):
            chunk = value[start : start + 1000].strip()
            if chunk:
                segments.append({"location": f"Paragraph {paragraph}", "text": chunk})
    return segments


def parse_upload(filename: str, data: bytes) -> dict:
    extension = Path(filename).suffix.lower()
    if extension == ".txt":
        try:
            text = data.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            raise HTTPException(422, "Text files must use UTF-8 encoding.")
        if not text or "\x00" in text or len(text) > MAX_TEXT:
            raise HTTPException(422, "Provide non-empty text, up to 200,000 characters.")
        return {
            "kind": "text",
            "status": "ready",
            "text": text,
            "segments": text_segments(text),
            "media_type": "text/plain",
        }
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(422, "This file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise HTTPException(422, "Upload an unencrypted PDF.")
            if len(reader.pages) > 100:
                raise HTTPException(422, "PDFs may contain at most 100 pages.")
            segments = []
            total = 0
            for number, page in enumerate(reader.pages, 1):
                text = (page.extract_text() or "").replace("\x00", "").strip()
                total += len(text)
                if total > MAX_TEXT:
                    raise HTTPException(422, "PDF text exceeds 200,000 characters.")
                segments.extend(
                    {"location": f"Page {number}", "text": chunk["text"]}
                    for chunk in text_segments(text)
                )
        except HTTPException:
            raise
        except Exception:  # noqa: BLE001 — normalize third-party parser errors at this boundary
            raise HTTPException(422, "Could not read this PDF. Try another file.")
        return {
            "kind": "pdf",
            "status": "ready" if segments else "needs_text",
            "text": "\n\n".join(s["text"] for s in segments),
            "segments": segments,
            "media_type": "application/pdf",
        }
    if extension in {".png", ".jpg", ".jpeg", ".webp"}:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data)) as img:
                    if img.format not in {"PNG", "JPEG", "WEBP"}:
                        raise ValueError("Unsupported image")
                    media_type = Image.MIME[img.format]
                    img.verify()
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            Image.DecompressionBombWarning,
            Image.DecompressionBombError,
        ):
            raise HTTPException(422, "This file is not a supported, valid image.")
        return {
            "kind": "image",
            "status": "needs_text",
            "text": "",
            "segments": [],
            "media_type": media_type,
        }
    raise HTTPException(415, "Supported files: PDF, TXT, PNG, JPG, and WEBP.")
