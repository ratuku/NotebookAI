from io import BytesIO

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import func, select

from notebook_backend.config import settings
from notebook_backend.models.entities import Notebook, Question, Source, User


def path(notebook):
    return f"/api/v1/notebooks/{notebook}"


def add_text(client, notebook, text="Plants convert sunlight into energy through photosynthesis."):
    response = client.post(
        f"{path(notebook)}/sources/text", json={"title": "Biology", "text": text}
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_notebook_lifecycle(client, notebook):
    assert client.get(path(notebook)).json()["source_count"] == 0
    response = client.patch(path(notebook), json={"title": "  Botany  ", "description": "My notes"})
    assert response.json()["title"] == "Botany"
    assert any(n["id"] == notebook for n in client.get("/api/v1/notebooks").json())
    assert client.delete(path(notebook)).status_code == 204
    assert client.get(path(notebook)).status_code == 404


@pytest.mark.parametrize("payload", [{"title": "  "}, {"title": "x" * 161}, {}])
def test_invalid_notebook(client, payload):
    assert client.post("/api/v1/notebooks", json=payload).status_code == 422


def test_cited_answer_and_history(client, notebook):
    source_id = add_text(client, notebook)
    assert client.get(path(notebook)).json()["source_count"] == 1
    response = client.post(
        f"{path(notebook)}/questions",
        json={"question": "How does photosynthesis use sunlight?", "source_ids": [source_id]},
    )
    assert response.status_code == 201
    answer = response.json()
    assert answer["mode"] == "extractive"
    assert answer["citations"][0]["source_id"] == source_id
    assert answer["citations"][0]["location"] == "Paragraph 1"
    assert "Plants convert sunlight" in answer["answer"]
    assert client.get(f"{path(notebook)}/questions").json() == [answer]
    assert client.get(f"{path(notebook)}/sources/{source_id}/file").text.startswith("Plants")


def test_unknown_evidence_abstains(client, notebook):
    source = add_text(client, notebook)
    result = client.post(
        f"{path(notebook)}/questions",
        json={"question": "Who invented jazz?", "source_ids": [source]},
    ).json()
    assert result["citations"] == []
    assert "couldn’t find" in result["answer"]


def test_selection_and_notebook_isolation(client, notebook):
    source = add_text(client, notebook)
    other = client.post("/api/v1/notebooks", json={"title": "Other"}).json()["id"]
    foreign_source = add_text(client, other, "Photosynthesis is a secret in the other notebook.")
    assert client.get(f"{path(notebook)}/sources/{foreign_source}").status_code == 404
    assert client.get(f"{path(notebook)}/sources/{foreign_source}/file").status_code == 404
    assert client.delete(f"{path(notebook)}/sources/{foreign_source}").status_code == 404
    assert (
        client.post(
            f"{path(notebook)}/questions",
            json={"question": "photosynthesis", "source_ids": [foreign_source]},
        ).status_code
        == 404
    )
    excluded = add_text(
        client, notebook, "Photosynthesis contains confidential excluded information."
    )
    response = client.post(
        f"{path(notebook)}/questions", json={"question": "photosynthesis", "source_ids": [source]}
    ).json()
    assert excluded not in [c["source_id"] for c in response["citations"]]
    assert "confidential" not in response["answer"]


def test_other_users_notebooks_are_hidden(client, db):
    owner = User(username="future-user")
    db.add(owner)
    db.flush()
    private = Notebook(user_id=owner.id, title="Private")
    db.add(private)
    db.commit()
    assert client.get(path(private.id)).status_code == 404
    assert private.id not in [n["id"] for n in client.get("/api/v1/notebooks").json()]


@pytest.mark.parametrize("question,ids", [("   ", ["x"]), ("hi", []), ("x" * 2001, ["x"])])
def test_invalid_question(client, notebook, question, ids):
    assert (
        client.post(
            f"{path(notebook)}/questions", json={"question": question, "source_ids": ids}
        ).status_code
        == 422
    )


def test_delete_cascades_and_keeps_historical_quotes(client, notebook, db):
    source = add_text(client, notebook)
    client.post(
        f"{path(notebook)}/questions", json={"question": "sunlight", "source_ids": [source]}
    )
    client.delete(f"{path(notebook)}/sources/{source}")
    assert client.get(f"{path(notebook)}/questions").json()[0]["citations"][0]["excerpt"]
    add_text(client, notebook)
    client.delete(path(notebook))
    assert (
        db.scalar(select(func.count()).select_from(Source).where(Source.notebook_id == notebook))
        == 0
    )
    assert (
        db.scalar(
            select(func.count()).select_from(Question).where(Question.notebook_id == notebook)
        )
        == 0
    )


def test_upload_text_and_bad_files(client, notebook, monkeypatch):
    endpoint = f"{path(notebook)}/sources/upload"
    response = client.post(
        endpoint, files={"file": ("notes.txt", b"Sunlight helps plants.", "text/plain")}
    )
    assert response.status_code == 201
    assert response.json()["status"] == "ready"
    for name, content, status in [
        ("evil.exe", b"abc", 415),
        ("fake.pdf", b"abc", 422),
        ("fake.png", b"abc", 422),
        ("notes.txt", b"", 422),
        ("notes.txt", b"\xff", 422),
        ("notes.txt", b"a\x00", 422),
    ]:
        assert client.post(endpoint, files={"file": (name, content)}).status_code == status
    monkeypatch.setattr(settings, "max_upload_bytes", 2)
    assert client.post(endpoint, files={"file": ("big.txt", b"123")}).status_code == 413


def test_image_transcription(client, notebook):
    data = BytesIO()
    Image.new("RGB", (10, 10), "green").save(data, format="PNG")
    response = client.post(
        f"{path(notebook)}/sources/upload", files={"file": ("leaf.png", data.getvalue())}
    )
    assert response.status_code == 201
    source = response.json()
    assert source["status"] == "needs_text"
    endpoint = f"{path(notebook)}/sources/{source['id']}"
    assert client.get(f"{endpoint}/file").content == data.getvalue()
    question = {"question": "green leaf", "source_ids": [source["id"]]}
    assert client.post(f"{path(notebook)}/questions", json=question).status_code == 422
    response = client.put(
        f"{endpoint}/text", json={"title": "Leaf", "text": "A green leaf on a branch."}
    )
    assert response.json()["status"] == "ready"
    assert client.post(f"{path(notebook)}/questions", json=question).json()["citations"]


def pdf_bytes(with_text=False, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if with_text:
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        content = DecodedStreamObject()
        content.set_data(b"BT /F1 12 Tf 20 200 Td (Photosynthesis needs sunlight.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(content)
    if encrypted:
        writer.encrypt("secret")
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


def test_pdf_page_citation_and_scanned_status(client, notebook):
    endpoint = f"{path(notebook)}/sources/upload"
    source = client.post(endpoint, files={"file": ("biology.pdf", pdf_bytes(True))}).json()
    assert source["status"] == "ready"
    response = client.post(
        f"{path(notebook)}/questions",
        json={"question": "photosynthesis", "source_ids": [source["id"]]},
    ).json()
    assert response["citations"][0]["location"] == "Page 1"
    assert (
        client.post(endpoint, files={"file": ("scan.pdf", pdf_bytes())}).json()["status"]
        == "needs_text"
    )
    assert (
        client.post(endpoint, files={"file": ("secret.pdf", pdf_bytes(encrypted=True))}).status_code
        == 422
    )


def test_health_and_cors(client):
    assert client.get("/health").json() == {"status": "ok"}
    allowed = client.options(
        "/api/v1/notebooks",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    denied = client.options(
        "/api/v1/notebooks",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in denied.headers


def test_pasted_binary_null_is_rejected_before_database_write(client, notebook):
    response = client.post(
        f"{path(notebook)}/sources/text", json={"title": "Notes", "text": "hello\x00world"}
    )
    assert response.status_code == 422
    assert client.get(f"{path(notebook)}/sources").json() == []
