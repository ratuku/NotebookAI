import hashlib
from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient
from qdrant_client import models as m

from notebook_ai.chunking import chunk_segments, fingerprint
from notebook_ai.providers import AIError, Provider
from notebook_ai.retrieval import bm25, fuse_and_diversify

ABSTAIN = "I couldn’t find enough evidence in the selected sources to answer this question."


def equals(key, value):
    return m.FieldCondition(key=key, match=m.MatchValue(value=value))


class RagPipeline:
    def __init__(
        self, client: QdrantClient, provider: Provider, top_k: int = 6, min_score: float = 0.35
    ):
        self.client, self.provider = client, provider
        self.top_k, self.min_score = top_k, min_score
        self.collection = "sources_" + hashlib.sha256(provider.model_key.encode()).hexdigest()[:16]
        self.lock = RLock()

    def version(self, source: dict) -> str:
        # Title participates so renaming a transcription refreshes citation metadata.
        return fingerprint(source["segments"], self.provider.model_key + source["title"])

    def scope(self, user_id: str, notebook_id: str, versions: dict[str, str]) -> m.Filter:
        return m.Filter(
            must=[
                equals("user_id", user_id),
                equals("notebook_id", notebook_id),
                m.Filter(
                    should=[
                        m.Filter(must=[equals("source_id", sid), equals("version", version)])
                        for sid, version in versions.items()
                    ]
                ),
            ]
        )

    def index(self, source: dict, force: bool = False) -> tuple[str, int]:
        with self.lock:
            version = self.version(source)
            chunks = chunk_segments(
                source["segments"], token_count=getattr(self.provider, "token_count", None)
            )
            if not chunks:
                raise AIError("This source has no readable text. Add a transcription first.")
            scope = self.scope(source["user_id"], source["notebook_id"], {source["id"]: version})
            if self.client.collection_exists(self.collection) and not force:
                count = self.client.count(self.collection, count_filter=scope, exact=True).count
                if count == len(chunks):
                    return version, count
            vectors = self.provider.embed([c["text"] for c in chunks])
            if len(vectors) != len(chunks):
                raise AIError("Incomplete embeddings; source was not indexed.")
            if not self.client.collection_exists(self.collection):
                self.client.create_collection(
                    self.collection,
                    vectors_config=m.VectorParams(size=len(vectors[0]), distance=m.Distance.COSINE),
                )
            info = self.client.get_collection(self.collection)
            if info.config.params.vectors.size != len(vectors[0]):
                raise AIError(
                    "Embedding dimensions changed. Use a new embedding model/version name."
                )
            points = []
            for chunk, vector in zip(chunks, vectors, strict=True):
                key = str(uuid5(NAMESPACE_URL, f"{source['id']}:{version}:{chunk['chunk_index']}"))
                points.append(
                    m.PointStruct(
                        id=key,
                        vector=vector,
                        payload={
                            **chunk,
                            "source_id": source["id"],
                            "source_title": source["title"],
                            "notebook_id": source["notebook_id"],
                            "user_id": source["user_id"],
                            "version": version,
                            "url": source.get("url"),
                            "kind": source["kind"],
                        },
                    )
                )
            for start in range(0, len(points), 64):
                self.client.upsert(self.collection, points[start : start + 64], wait=True)
            # Only retire old versions after every new point has been stored.
            self.client.delete(
                self.collection,
                m.FilterSelector(
                    filter=m.Filter(
                        must=[
                            equals("source_id", source["id"]),
                            equals("user_id", source["user_id"]),
                        ],
                        must_not=[equals("version", version)],
                    )
                ),
                wait=True,
            )
            return version, len(points)

    def delete(self, user_id: str, notebook_id: str, source_id: str | None = None):
        with self.lock:
            if self.client.collection_exists(self.collection):
                conditions = [equals("user_id", user_id), equals("notebook_id", notebook_id)]
                if source_id:
                    conditions.append(equals("source_id", source_id))
                self.client.delete(
                    self.collection, m.FilterSelector(filter=m.Filter(must=conditions)), wait=True
                )

    def retrieve(self, question: str, user_id: str, notebook_id: str, versions: dict[str, str]):
        if not versions:
            return []
        with self.lock:
            if not self.client.collection_exists(self.collection):
                raise AIError("Vector index is missing. Reindex the selected sources.")
            scope = self.scope(user_id, notebook_id, versions)
            vector = self.provider.embed_query(question)
            dense = self.client.query_points(
                self.collection,
                query=vector,
                query_filter=scope,
                limit=30,
                score_threshold=self.min_score,
                with_vectors=True,
            ).points
            # Local corpus BM25 is exact and source-scoped; cap instead of silently truncating.
            all_records, offset = [], None
            while True:
                page, offset = self.client.scroll(
                    self.collection,
                    scroll_filter=scope,
                    limit=256,
                    offset=offset,
                    with_vectors=True,
                )
                all_records.extend(page)
                if len(all_records) > 10_000:
                    raise AIError(
                        "Select fewer sources: local hybrid retrieval supports 10,000 chunks."
                    )
                if offset is None:
                    break
            lexical = bm25(question, [r.payload["text"] for r in all_records])
            ranked = sorted(
                zip(all_records, lexical, strict=True), key=lambda pair: pair[1], reverse=True
            )
            lexical_ids = [str(r.id) for r, score in ranked if score > 0][:30]
            records = {str(r.id): r for r in all_records}
            return fuse_and_diversify([str(r.id) for r in dense], lexical_ids, records, self.top_k)

    def answer(self, question: str, user_id: str, notebook_id: str, versions: dict[str, str]):
        matches = self.retrieve(question, user_id, notebook_id, versions)
        if not matches:
            return ABSTAIN, []
        evidence = [
            {
                "id": str(r.id),
                "text": r.payload["text"],
                "location": r.payload["location"],
                "title": r.payload["source_title"],
            }
            for r in matches
        ]
        draft = self.provider.generate(question, evidence)
        if draft.insufficient_evidence:
            return ABSTAIN, []
        if not draft.claims:
            raise AIError("The answer contained no supported claims. Please retry.")
        known = {str(r.id): r.payload for r in matches}
        cited, paragraphs = [], []
        for claim in draft.claims:
            if not claim.text.strip() or any(key not in known for key in claim.citations):
                raise AIError("The answer included an invalid citation. Please retry.")
            markers = []
            for key in dict.fromkeys(claim.citations):
                if key not in cited:
                    cited.append(key)
                markers.append(f"[{cited.index(key) + 1}]")
            paragraphs.append(claim.text + " " + " ".join(markers))
        citations = [
            {
                "source_id": known[key]["source_id"],
                "source_title": known[key]["source_title"],
                "location": known[key]["location"],
                "excerpt": known[key]["text"],
                "chunk_id": key,
                "source_version": known[key]["version"],
                "url": known[key].get("url"),
            }
            for key in cited
        ]
        return "\n\n".join(paragraphs), citations
