from fastapi import APIRouter
from sqlalchemy import select

from notebook_backend.controllers.notebooks import DB, admin_id, get_notebook, get_source
from notebook_backend.models.entities import Notebook, Source
from notebook_backend.services.ingestion import index_source
from notebook_backend.views.schemas import ReindexInput, SourceView

router = APIRouter(prefix="/api/v1", tags=["ingestion"])


@router.post("/notebooks/{notebook_id}/sources/{source_id}/ingest", response_model=SourceView)
def ingest_one(notebook_id: str, source_id: str, payload: ReindexInput, db: DB):
    source = get_source(db, notebook_id, source_id)
    return index_source(db, source, admin_id(db), force=payload.force, reextract=payload.reextract)


@router.post("/ingestion/rebuild", response_model=list[SourceView])
def rebuild(payload: ReindexInput, db: DB):
    user_id = admin_id(db)
    statement = (
        select(Source.id, Source.notebook_id).join(Notebook).where(Notebook.user_id == user_id)
    )
    if payload.notebook_id:
        get_notebook(db, payload.notebook_id)
        statement = statement.where(Source.notebook_id == payload.notebook_id)
    # Materialize IDs only; process each source transaction separately and report every outcome.
    targets = db.execute(statement.order_by(Source.created_at)).all()
    results = []
    for source_id, notebook_id in targets:
        source = db.get(Source, source_id)
        if source:
            results.append(
                SourceView.model_validate(
                    index_source(
                        db, source, user_id, force=payload.force, reextract=payload.reextract
                    )
                )
            )
    return results
