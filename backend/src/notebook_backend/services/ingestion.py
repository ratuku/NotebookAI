import logging
from functools import lru_cache

from fastapi import HTTPException
from notebook_ai.extraction import ExtractionError, parse_upload, text_segments
from notebook_ai.pipeline import RagPipeline
from notebook_ai.providers import AIError, GroqProvider
from notebook_ai.urls import extract_page
from qdrant_client import QdrantClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from notebook_backend.config import settings
from notebook_backend.models.entities import Notebook, Source

logger = logging.getLogger(__name__)


@lru_cache
def get_pipeline() -> RagPipeline:
    provider = GroqProvider(
        settings.groq_api_key.get_secret_value(),
        settings.groq_model,
        settings.embedding_model,
        settings.model_cache_path,
    )
    client = (
        QdrantClient(url=settings.qdrant_url, timeout=30)
        if settings.qdrant_url
        else QdrantClient(path=settings.qdrant_path, force_disable_check_same_thread=True)
    )
    return RagPipeline(client, provider, settings.rag_top_k, settings.rag_min_score)


def lock_notebook(db: Session, notebook_id: str):
    # Serialize mutations/index publication in one notebook across backend processes.
    db.execute(select(Notebook).where(Notebook.id == notebook_id).with_for_update()).scalar_one()


def snapshot(source: Source, user_id: str) -> dict:
    return {
        "id": source.id,
        "notebook_id": source.notebook_id,
        "user_id": user_id,
        "title": source.title,
        "segments": source.segments,
        "kind": source.kind,
        "url": source.url,
    }


def index_source(db: Session, source: Source, user_id: str, *, force=False, reextract=False):
    lock_notebook(db, source.notebook_id)
    db.refresh(source)
    if settings.ai_mode != "rag":
        source.index_status = "disabled"
        db.commit()
        return source
    try:
        source.index_status = "processing"
        source.index_error = None
        if reextract and source.original is not None and not source.text_override:
            if source.kind == "url":
                parsed = extract_page(source.original, source.media_type)
            else:
                extension = {"text": "txt", "pdf": "pdf", "pptx": "pptx", "image": "png"}[
                    source.kind
                ]
                parsed = parse_upload("source." + extension, source.original)
            source.text, source.segments, source.status = (
                parsed["text"],
                parsed["segments"],
                parsed["status"],
            )
        if not source.segments and source.text:
            source.segments = text_segments(source.text)
        if source.status != "ready":
            source.index_status = "needs_text"
            source.index_version = None
            source.chunk_count = 0
        else:
            version, count = get_pipeline().index(snapshot(source, user_id), force=force)
            source.index_version, source.chunk_count = version, count
            source.index_status = "ready"
    except Exception as exc:  # noqa: BLE001 -- persist recoverable ingestion failures
        source.index_status = "failed"
        source.index_version = None
        source.chunk_count = 0
        source.index_error = (
            str(exc)
            if isinstance(exc, (AIError, ExtractionError))
            else "Vector indexing failed. Retry ingestion; check the backend service."
        )
        logger.warning("Indexing failed for source %s (%s)", source.id, type(exc).__name__)
    db.commit()
    return source


def remove_vectors(user_id, notebook_id, source_id=None):
    if settings.ai_mode != "rag":
        return
    try:
        get_pipeline().delete(user_id, notebook_id, source_id)
    except Exception as exc:
        raise HTTPException(503, "Vector cleanup failed. Please retry deletion.") from exc
