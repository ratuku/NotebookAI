import math
import re
from collections import Counter

STOP = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "to",
    "of",
    "and",
    "or",
    "in",
    "on",
    "for",
    "it",
    "this",
    "that",
    "what",
    "which",
    "how",
    "do",
    "does",
    "can",
    "you",
    "me",
    "about",
    "tell",
    "please",
}


def terms(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOP]


def bm25(query: str, texts: list[str]) -> list[float]:
    """BM25 with positive Robertson/Lucene IDF, k1=1.5, b=0.75."""
    docs = [terms(text) for text in texts]
    if not docs:
        return []
    avg = sum(map(len, docs)) / len(docs) or 1
    df = Counter(t for doc in docs for t in set(doc))
    result = []
    for doc in docs:
        counts = Counter(doc)
        score = 0.0
        for term in set(terms(query)):
            frequency = counts[term]
            idf = math.log(1 + (len(docs) - df[term] + 0.5) / (df[term] + 0.5))
            score += idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * len(doc) / avg))
        result.append(score)
    return result


def cosine(a: list[float], b: list[float]) -> float:
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / denominator if denominator else 0


def fuse_and_diversify(
    dense_ids: list[str], lexical_ids: list[str], records: dict, top_k: int
) -> list:
    # Reciprocal rank fusion avoids comparing unrelated dense and BM25 score scales.
    scores: dict[str, float] = {}
    for ranking in (dense_ids, lexical_ids):
        for rank, key in enumerate(ranking, 1):
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
    chosen = []
    maximum = max(scores.values(), default=1)
    while scores and len(chosen) < top_k:

        def utility(key):
            redundancy = max((cosine(records[key].vector, r.vector) for r in chosen), default=0)
            return 0.75 * scores[key] / maximum - 0.25 * redundancy

        best = max(scores, key=utility)
        candidate = records[best]
        del scores[best]
        if not any(candidate.payload["text"] == r.payload["text"] for r in chosen):
            chosen.append(candidate)
    return chosen
