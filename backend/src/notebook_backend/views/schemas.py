from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=160, pattern=r"^[^\x00]*$"),
]
Content = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200_000, pattern=r"^[^\x00]*$"
    ),
]


class NotebookInput(BaseModel):
    title: Title
    description: str = Field(default="", max_length=2000, pattern=r"^[^\x00]*$")


class NotebookView(NotebookInput):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    source_count: int


class TextSourceInput(BaseModel):
    title: Title
    text: Content


class URLSourceInput(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class ReindexInput(BaseModel):
    force: bool = True
    reextract: bool = True
    notebook_id: str | None = None


class SourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    notebook_id: str
    title: str
    kind: Literal["text", "pdf", "pptx", "url", "image"]
    status: Literal["ready", "needs_text"]
    index_status: str
    index_error: str | None = None
    chunk_count: int = 0
    url: str | None = None
    created_at: datetime


class SourceDetail(SourceView):
    text: str
    segments: list[dict]


RetrievalMethod = Literal["normal", "reranking"]


class QuestionInput(BaseModel):
    retrieval_method: RetrievalMethod = "normal"
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=2000, pattern=r"^[^\x00]*$"
        ),
    ]
    source_ids: list[str] = Field(min_length=1, max_length=100)


class Citation(BaseModel):
    source_id: str
    source_title: str
    location: str
    excerpt: str
    chunk_id: str | None = None
    source_version: str | None = None
    url: str | None = None


class RetrievalStats(BaseModel):
    chunks_found: int = Field(ge=0)
    candidates_count: int = Field(ge=0)
    chunks_selected: int = Field(ge=0)
    retrieval_ms: float = Field(ge=0)
    reranking_ms: float = Field(ge=0)


class QuestionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    question: str
    answer: str
    source_ids: list[str]
    citations: list[Citation]
    mode: str
    retrieval_method: str
    retrieval_stats: RetrievalStats | None = None
    created_at: datetime


class ArtifactInput(BaseModel):
    kind: Literal["report", "quiz"]
    topic: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    source_ids: list[str] = Field(min_length=1, max_length=100)
    retrieval_method: RetrievalMethod = "normal"
    question_count: int = Field(default=5, ge=3, le=10)


class ArtifactView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    notebook_id: str
    kind: str
    title: str
    topic: str
    retrieval_method: str
    retrieval_stats: RetrievalStats | None = None
    source_ids: list[str]
    content: dict
    citations: list[Citation]
    created_at: datetime
