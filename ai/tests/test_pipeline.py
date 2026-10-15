import pytest
from qdrant_client import QdrantClient

from notebook_ai.chunking import chunk_segments
from notebook_ai.pipeline import RagPipeline
from notebook_ai.providers import AIError, AnswerDraft, Claim
from notebook_ai.retrieval import bm25


class FakeProvider:
    model_key = "deterministic-test-v1"
    calls = 0
    bad_citation = False
    fail = False

    def embed(self, texts):
        if self.fail:
            raise AIError("Test embedding unavailable")
        self.calls += 1
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text):
        words = text.lower()
        groups = [
            ("sun", "solar", "photosynthesis", "plant"),
            ("moon", "lunar"),
            ("ocean", "sea"),
            ("secret", "classified"),
            ("dog", "canine"),
        ]
        vector = [float(any(word in words for word in group)) for group in groups]
        return vector + [float(not any(vector))]

    def generate(self, question, evidence):
        return AnswerDraft(
            insufficient_evidence=False,
            claims=[
                Claim(
                    text=evidence[0]["text"],
                    citations=["invented" if self.bad_citation else evidence[0]["id"]],
                )
            ],
        )


@pytest.fixture()
def pipeline():
    client = QdrantClient(":memory:")
    result = RagPipeline(client, FakeProvider(), top_k=3, min_score=0.5)
    yield result
    client.close()


def source(id="s1", notebook="n1", text="Plants use sunlight for photosynthesis.", user="u1"):
    return {
        "id": id,
        "notebook_id": notebook,
        "user_id": user,
        "kind": "pdf",
        "title": id,
        "segments": [{"location": "Page 2", "text": text}],
    }


def test_chunks_preserve_locations_overlap_and_tail():
    text = "A sentence about plants. " * 180 + "Unique final words."
    chunks = chunk_segments(
        [{"location": "Page 1", "text": text}, {"location": "Page 2", "text": "Another page."}]
    )
    assert all(len(c["text"]) <= 1200 for c in chunks)
    assert chunks[-1]["location"] == "Page 2"
    assert "Unique final words." in chunks[-2]["text"]
    assert chunks[1]["start"] < chunks[0]["end"]
    assert len({c["chunk_index"] for c in chunks}) == len(chunks)


def test_index_idempotency_replacement_and_semantic_query(pipeline):
    item = source()
    version, count = pipeline.index(item)
    assert count == 1
    pipeline.index(item)
    assert pipeline.provider.calls == 1
    matches = pipeline.retrieve("solar energy", "u1", "n1", {"s1": version})
    assert matches[0].payload["location"] == "Page 2"
    item["segments"][0]["text"] = "Lunar craters cover the moon."
    changed, _ = pipeline.index(item)
    assert changed != version
    assert pipeline.client.count(pipeline.collection).count == 1
    assert pipeline.retrieve("solar", "u1", "n1", {"s1": version}) == []


def test_scope_includes_owner_notebook_selection_and_version(pipeline):
    first, _ = pipeline.index(source())
    pipeline.index(source("s2", notebook="n2"))
    pipeline.index(source("s3", user="u2"))
    pipeline.index(source("s4"))
    matches = pipeline.retrieve("plants", "u1", "n1", {"s1": first})
    assert {r.payload["source_id"] for r in matches} == {"s1"}
    assert pipeline.retrieve("plants", "u2", "n1", {"s1": first}) == []
    assert pipeline.retrieve("plants", "u1", "n1", {}) == []


def test_citations_are_copied_from_actual_chunks_and_invalid_ids_fail(pipeline):
    version, _ = pipeline.index(source())
    answer, citations = pipeline.answer("plants", "u1", "n1", {"s1": version})
    assert "[1]" in answer
    assert citations[0]["location"] == "Page 2"
    assert citations[0]["source_version"] == version
    assert citations[0]["excerpt"] == source()["segments"][0]["text"]
    pipeline.provider.bad_citation = True
    with pytest.raises(AIError, match="invalid citation"):
        pipeline.answer("plants", "u1", "n1", {"s1": version})


def test_no_evidence_abstains_and_delete_removes_points(pipeline):
    version, _ = pipeline.index(source())
    answer, citations = pipeline.answer("ocean", "u1", "n1", {"s1": version})
    assert "enough evidence" in answer and citations == []
    pipeline.delete("u1", "n1", "s1")
    assert pipeline.client.count(pipeline.collection).count == 0


def test_bm25_exact_identifier_complements_dense(pipeline):
    v1, _ = pipeline.index(source("s1", text="Plants use sunlight. Reference ZXQ913."))
    v2, _ = pipeline.index(source("s2", text="Plants absorb solar energy."))
    matches = pipeline.retrieve("ZXQ913", "u1", "n1", {"s1": v1, "s2": v2})
    assert matches[0].payload["source_id"] == "s1"
    assert bm25("ZXQ913", ["ZXQ913", "sun"])[0] > 0


def test_duplicate_chunks_are_not_repeated(pipeline):
    versions = {sid: pipeline.index(source(sid))[0] for sid in ["s1", "s2", "s3"]}
    assert len(pipeline.retrieve("plants", "u1", "n1", versions)) == 1


def test_partial_vector_write_retry_preserves_old_version(pipeline, monkeypatch):
    item = source()
    old_version, _ = pipeline.index(item)
    item["segments"] = [
        {"location": f"Page {i}", "text": f"Solar energy supports plants, observation {i}."}
        for i in range(70)
    ]
    upsert = pipeline.client.upsert
    calls = 0

    def interrupted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Interrupted vector write")
        return upsert(*args, **kwargs)

    monkeypatch.setattr(pipeline.client, "upsert", interrupted)
    with pytest.raises(RuntimeError, match="Interrupted"):
        pipeline.index(item)
    old_matches = pipeline.retrieve("plants", "u1", "n1", {"s1": old_version})
    assert len(old_matches) == 1
    assert old_matches[0].payload["text"] == source()["segments"][0]["text"]
    monkeypatch.setattr(pipeline.client, "upsert", upsert)
    new_version, count = pipeline.index(item)
    assert count == 70
    assert pipeline.client.count(pipeline.collection).count == 70
    assert pipeline.retrieve("plants", "u1", "n1", {"s1": old_version}) == []
    assert pipeline.retrieve("plants", "u1", "n1", {"s1": new_version})


def test_reranking_changes_order_using_same_scoped_candidates(pipeline, monkeypatch):
    versions = {
        f"s{i}": pipeline.index(source(f"s{i}", text=f"Plants use solar energy. Study {i}."))[0]
        for i in range(5)
    }
    normal = pipeline.retrieve("plants", "u1", "n1", versions)
    captured = []

    def rerank(question, evidence):
        captured.extend(evidence)
        return [item["id"] for item in reversed(evidence)]

    monkeypatch.setattr(pipeline.provider, "rerank", rerank, raising=False)
    advanced = pipeline.retrieve("plants", "u1", "n1", versions, "reranking")
    assert len(captured) == 5
    assert [str(r.id) for r in advanced] == [e["id"] for e in reversed(captured)][:3]
    assert [str(r.id) for r in normal] == [e["id"] for e in captured][:3]
    monkeypatch.setattr(pipeline.provider, "rerank", lambda *args: ["foreign"])
    with pytest.raises(AIError, match="invalid passage IDs"):
        pipeline.retrieve("plants", "u1", "n1", versions, "reranking")


def test_retrieval_metrics_counts_timing_and_no_generation_time(pipeline, monkeypatch):
    from notebook_ai import pipeline as module

    versions = {
        f"s{i}": pipeline.index(source(f"s{i}", text=f"Plants use solar energy. Observation {i}."))[
            0
        ]
        for i in range(5)
    }
    ticks = iter([1.0, 1.25, 1.75, 2.0])
    monkeypatch.setattr(module, "perf_counter", lambda: next(ticks))
    monkeypatch.setattr(
        pipeline.provider, "rerank", lambda q, e: [x["id"] for x in reversed(e)], raising=False
    )
    stats = {}
    pipeline.answer("plants", "u1", "n1", versions, "reranking", metrics=stats)
    assert stats == {
        "chunks_found": 5,
        "candidates_count": 5,
        "chunks_selected": 3,
        "retrieval_ms": 1000.0,
        "reranking_ms": 500.0,
    }
    empty = {}
    assert pipeline.retrieve("plants", "u1", "n1", {}, metrics=empty) == []
    assert empty["chunks_found"] == 0 and empty["chunks_selected"] == 0
