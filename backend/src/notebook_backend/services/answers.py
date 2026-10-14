import re
from collections import Counter
from math import log

from notebook_backend.models.entities import Source

STOP_WORDS = {
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
    "summarize",
    "summary",
    "please",
    "source",
    "sources",
}


def tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"\w+", text.lower()) if word not in STOP_WORDS}


def answer_question(question: str, sources: list[Source]) -> tuple[str, list[dict]]:
    chunks = [(source, segment) for source in sources for segment in source.segments]
    query = tokens(question)
    frequency = Counter(word for _, chunk in chunks for word in tokens(chunk["text"]))
    ranked = []
    for source, chunk in chunks:
        overlap = query & tokens(chunk["text"])
        score = sum(log(1 + len(chunks) / frequency[word]) for word in overlap)
        if score:
            ranked.append((score, source, chunk))
    ranked.sort(key=lambda item: item[0], reverse=True)
    citations = [
        {
            "source_id": s.id,
            "source_title": s.title,
            "location": c["location"],
            "excerpt": c["text"],
        }
        for _, s, c in ranked[:3]
    ]
    if not citations:
        return (
            (
                "I couldn’t find a matching passage in the selected sources. "
                "Try using words from your documents or selecting another source."
            ),
            [],
        )
    answer = "Here are the closest matching passages from your selected sources:\n\n"
    answer += "\n\n".join(f"[{i}] {c['excerpt']}" for i, c in enumerate(citations, 1))
    return answer, citations
