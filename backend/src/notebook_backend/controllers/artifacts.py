from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from notebook_ai.artifacts import export_artifact, generate_artifact
from notebook_ai.providers import AIError
from sqlalchemy import select

from notebook_backend.config import settings
from notebook_backend.controllers.notebooks import DB, admin_id, get_notebook
from notebook_backend.models.entities import Artifact, Source
from notebook_backend.services import ingestion
from notebook_backend.views.schemas import ArtifactInput, ArtifactView

router = APIRouter(prefix="/api/v1/notebooks", tags=["artifacts"])


@router.post("/{notebook_id}/artifacts", response_model=ArtifactView, status_code=201)
def create_artifact(notebook_id: str, payload: ArtifactInput, db: DB):
    get_notebook(db, notebook_id)
    if settings.ai_mode != "rag":
        raise HTTPException(422, "Artifact generation requires RAG mode and a Groq API key.")
    ingestion.lock_notebook(db, notebook_id)
    ids = list(dict.fromkeys(payload.source_ids))
    sources = db.scalars(
        select(Source).where(Source.notebook_id == notebook_id, Source.id.in_(ids))
    ).all()
    if len(sources) != len(ids):
        raise HTTPException(404, "One or more sources do not belong to this notebook.")
    user_id = admin_id(db)
    try:
        pipeline = ingestion.get_pipeline()
        if any(
            s.index_status != "ready"
            or s.index_version != pipeline.version(ingestion.snapshot(s, user_id))
            for s in sources
        ):
            raise HTTPException(409, "Index the selected sources before generating an artifact.")
        retrieval_stats = {}
        title, content, citations = generate_artifact(
            pipeline,
            payload.kind,
            payload.topic,
            user_id,
            notebook_id,
            {s.id: s.index_version for s in sources},
            payload.retrieval_method,
            payload.question_count,
            metrics=retrieval_stats,
        )
    except AIError as exc:
        raise HTTPException(503, str(exc)) from exc
    artifact = Artifact(
        notebook_id=notebook_id,
        title=title,
        content=content,
        citations=citations,
        kind=payload.kind,
        topic=payload.topic,
        source_ids=ids,
        retrieval_method=payload.retrieval_method,
        retrieval_stats=retrieval_stats,
    )
    db.add(artifact)
    db.commit()
    return artifact


@router.get("/{notebook_id}/artifacts", response_model=list[ArtifactView])
def list_artifacts(notebook_id: str, db: DB):
    get_notebook(db, notebook_id)
    return db.scalars(
        select(Artifact)
        .where(Artifact.notebook_id == notebook_id)
        .order_by(Artifact.created_at.desc())
    ).all()


def owned_artifact(db, notebook_id, artifact_id):
    get_notebook(db, notebook_id)
    artifact = db.scalar(
        select(Artifact).where(Artifact.id == artifact_id, Artifact.notebook_id == notebook_id)
    )
    if not artifact:
        raise HTTPException(404, "Artifact not found in this notebook.")
    return artifact


@router.get("/{notebook_id}/artifacts/{artifact_id}/download")
def download_artifact(
    notebook_id: str, artifact_id: str, db: DB, format: Literal["markdown", "html"] = "markdown"
):
    artifact = owned_artifact(db, notebook_id, artifact_id)
    extension = "html" if format == "html" else "md"
    return Response(
        export_artifact(artifact, format),
        media_type="text/html" if format == "html" else "text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.kind}-{artifact.id}.{extension}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
    )


@router.delete("/{notebook_id}/artifacts/{artifact_id}", status_code=204)
def delete_artifact(notebook_id: str, artifact_id: str, db: DB):
    artifact = owned_artifact(db, notebook_id, artifact_id)
    db.delete(artifact)
    db.commit()
