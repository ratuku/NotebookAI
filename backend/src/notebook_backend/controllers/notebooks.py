from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from notebook_ai.extraction import ExtractionError
from notebook_ai.providers import AIError
from notebook_ai.urls import extract_page, fetch_page
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from notebook_backend.config import settings
from notebook_backend.database import get_db
from notebook_backend.models.entities import Notebook, Question, Source, User
from notebook_backend.services.answers import answer_question
from notebook_backend.services.ingestion import (
    get_pipeline,
    index_source,
    lock_notebook,
    remove_vectors,
    snapshot,
)
from notebook_backend.services.sources import parse_upload, text_segments
from notebook_backend.views.schemas import (
    NotebookInput,
    NotebookView,
    QuestionInput,
    QuestionView,
    SourceDetail,
    SourceView,
    TextSourceInput,
    URLSourceInput,
)

router = APIRouter(prefix="/api/v1/notebooks", tags=["notebooks"])
DB = Annotated[Session, Depends(get_db)]


def admin_id(db: Session) -> str:
    user = db.scalar(select(User).where(User.username == "admin"))
    if not user:
        raise HTTPException(503, "Database not initialized. Run alembic upgrade head.")
    return user.id


def get_notebook(db: Session, notebook_id: str) -> Notebook:
    notebook = db.scalar(
        select(Notebook).where(Notebook.id == notebook_id, Notebook.user_id == admin_id(db))
    )
    if not notebook:
        raise HTTPException(404, "Notebook not found.")
    return notebook


def get_source(db: Session, notebook_id: str, source_id: str) -> Source:
    get_notebook(db, notebook_id)
    source = db.scalar(
        select(Source).where(Source.id == source_id, Source.notebook_id == notebook_id)
    )
    if not source:
        raise HTTPException(404, "Source not found in this notebook.")
    return source


def notebook_view(db: Session, notebook: Notebook) -> dict:
    count = db.scalar(
        select(func.count()).select_from(Source).where(Source.notebook_id == notebook.id)
    )
    return {
        "id": notebook.id,
        "title": notebook.title,
        "description": notebook.description,
        "created_at": notebook.created_at,
        "source_count": count,
    }


@router.get("", response_model=list[NotebookView])
def list_notebooks(db: DB):
    count = select(func.count(Source.id)).where(Source.notebook_id == Notebook.id).scalar_subquery()
    rows = db.execute(
        select(Notebook, count)
        .where(Notebook.user_id == admin_id(db))
        .order_by(Notebook.created_at.desc())
    ).all()
    return [
        {
            "id": n.id,
            "title": n.title,
            "description": n.description,
            "created_at": n.created_at,
            "source_count": c,
        }
        for n, c in rows
    ]


@router.post("", response_model=NotebookView, status_code=201)
def create_notebook(payload: NotebookInput, db: DB):
    notebook = Notebook(user_id=admin_id(db), **payload.model_dump())
    db.add(notebook)
    db.commit()
    return notebook_view(db, notebook)


@router.get("/{notebook_id}", response_model=NotebookView)
def read_notebook(notebook_id: str, db: DB):
    return notebook_view(db, get_notebook(db, notebook_id))


@router.patch("/{notebook_id}", response_model=NotebookView)
def update_notebook(notebook_id: str, payload: NotebookInput, db: DB):
    notebook = get_notebook(db, notebook_id)
    notebook.title = payload.title
    notebook.description = payload.description
    db.commit()
    return notebook_view(db, notebook)


@router.delete("/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: str, db: DB):
    notebook = get_notebook(db, notebook_id)
    lock_notebook(db, notebook_id)
    remove_vectors(admin_id(db), notebook_id)
    db.delete(notebook)
    db.commit()


@router.get("/{notebook_id}/sources", response_model=list[SourceView])
def list_sources(notebook_id: str, db: DB):
    get_notebook(db, notebook_id)
    return db.scalars(
        select(Source).where(Source.notebook_id == notebook_id).order_by(Source.created_at)
    ).all()


@router.post("/{notebook_id}/sources/text", response_model=SourceView, status_code=201)
def add_text(notebook_id: str, payload: TextSourceInput, db: DB):
    get_notebook(db, notebook_id)
    source = Source(
        notebook_id=notebook_id,
        title=payload.title,
        kind="text",
        text=payload.text,
        segments=text_segments(payload.text),
        status="ready",
    )
    db.add(source)
    db.commit()
    return index_source(db, source, admin_id(db))


@router.post("/{notebook_id}/sources/upload", response_model=SourceView, status_code=201)
def upload_source(notebook_id: str, file: UploadFile, db: DB):
    get_notebook(db, notebook_id)
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "Files must be 10 MB or smaller.")
    if not data:
        raise HTTPException(422, "The uploaded file is empty.")
    title = (
        (file.filename or "Untitled source")
        .replace("\x00", "")
        .replace("\\", "/")
        .rsplit("/", 1)[-1][:200]
    )
    source = Source(
        notebook_id=notebook_id,
        title=title or "Untitled source",
        original=data,
        **parse_upload(file.filename or "", data),
    )
    db.add(source)
    db.commit()
    return index_source(db, source, admin_id(db))


@router.get("/{notebook_id}/sources/{source_id}", response_model=SourceDetail)
def read_source(notebook_id: str, source_id: str, db: DB):
    return get_source(db, notebook_id, source_id)


@router.put("/{notebook_id}/sources/{source_id}/text", response_model=SourceDetail)
def supply_transcription(notebook_id: str, source_id: str, payload: TextSourceInput, db: DB):
    source = get_source(db, notebook_id, source_id)
    lock_notebook(db, notebook_id)
    db.refresh(source)
    source.text_override = True
    source.index_version = None
    source.index_status = "pending"
    source.title, source.text = payload.title, payload.text
    source.segments = text_segments(payload.text)
    source.status = "ready"
    db.commit()
    return index_source(db, source, admin_id(db))


@router.get("/{notebook_id}/sources/{source_id}/file")
def download_source(notebook_id: str, source_id: str, db: DB):
    source = get_source(db, notebook_id, source_id)
    return Response(
        content=source.original if source.original is not None else source.text.encode(),
        media_type="text/plain" if source.kind == "url" else (source.media_type or "text/plain"),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{notebook_id}/sources/{source_id}", status_code=204)
def delete_source(notebook_id: str, source_id: str, db: DB):
    source = get_source(db, notebook_id, source_id)
    lock_notebook(db, notebook_id)
    remove_vectors(admin_id(db), notebook_id, source_id)
    db.delete(source)
    db.commit()


@router.get("/{notebook_id}/questions", response_model=list[QuestionView])
def list_questions(notebook_id: str, db: DB):
    get_notebook(db, notebook_id)
    return db.scalars(
        select(Question).where(Question.notebook_id == notebook_id).order_by(Question.created_at)
    ).all()


@router.post("/{notebook_id}/questions", response_model=QuestionView, status_code=201)
def ask_question(notebook_id: str, payload: QuestionInput, db: DB):
    get_notebook(db, notebook_id)
    ids = list(dict.fromkeys(payload.source_ids))
    sources = db.scalars(
        select(Source).where(Source.notebook_id == notebook_id, Source.id.in_(ids))
    ).all()
    if len(sources) != len(ids):
        raise HTTPException(404, "One or more sources do not belong to this notebook.")
    if any(source.status != "ready" for source in sources):
        raise HTTPException(
            422, "Add a text transcription to these sources before asking questions."
        )
    mode = "extractive"
    retrieval_stats = None
    if settings.ai_mode == "rag":
        lock_notebook(db, notebook_id)
        for source in sources:
            db.refresh(source)
        try:
            pipeline = get_pipeline()
            if any(
                s.index_status != "ready"
                or s.index_version != pipeline.version(snapshot(s, admin_id(db)))
                for s in sources
            ):
                raise HTTPException(
                    409, "Some sources are not indexed. Retry ingestion before asking."
                )
            retrieval_stats = {}
            answer, citations = pipeline.answer(
                payload.question,
                admin_id(db),
                notebook_id,
                {s.id: s.index_version for s in sources},
                payload.retrieval_method,
                metrics=retrieval_stats,
            )
            mode = "rag"
        except AIError as exc:
            raise HTTPException(503, str(exc)) from exc
    else:
        if payload.retrieval_method != "normal":
            raise HTTPException(422, "Reranking requires RAG mode.")
        answer, citations = answer_question(payload.question, sources)
    question = Question(
        notebook_id=notebook_id,
        question=payload.question,
        source_ids=ids,
        answer=answer,
        citations=citations,
        mode=mode,
        retrieval_method=payload.retrieval_method,
        retrieval_stats=retrieval_stats,
    )
    db.add(question)
    db.commit()
    return question


@router.post("/{notebook_id}/sources/url", response_model=SourceView, status_code=201)
def add_url(notebook_id: str, payload: URLSourceInput, db: DB):
    get_notebook(db, notebook_id)
    try:
        final_url, data, media = fetch_page(payload.url)
        parsed = extract_page(data, media)
    except ExtractionError as exc:
        raise HTTPException(422, str(exc)) from exc
    source = Source(notebook_id=notebook_id, url=final_url, original=data, **parsed)
    db.add(source)
    db.commit()
    return index_source(db, source, admin_id(db))
