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


class SourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    notebook_id: str
    title: str
    kind: Literal["text", "pdf", "image"]
    status: Literal["ready", "needs_text"]
    created_at: datetime


class SourceDetail(SourceView):
    text: str
    segments: list[dict]


class QuestionInput(BaseModel):
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


class QuestionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    question: str
    answer: str
    source_ids: list[str]
    citations: list[Citation]
    mode: str
    created_at: datetime
