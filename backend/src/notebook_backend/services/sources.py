from fastapi import HTTPException
from notebook_ai.extraction import ExtractionError, text_segments  # noqa: F401
from notebook_ai.extraction import parse_upload as extract


def parse_upload(filename: str, data: bytes) -> dict:
    try:
        return extract(filename, data)
    except ExtractionError as exc:
        status = 415 if str(exc).startswith("Supported files") else 422
        raise HTTPException(status, str(exc)) from exc
