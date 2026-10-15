import hashlib
import json
import re

VERSION = "location-window-v2:1200:200:400tokens"


def fingerprint(segments: list[dict], model: str) -> str:
    return hashlib.sha256(
        json.dumps([VERSION, model, segments], sort_keys=True).encode()
    ).hexdigest()


def chunk_segments(
    segments: list[dict], size: int = 1200, overlap: int = 200, token_count=None
) -> list[dict]:
    """Character-bounded, overlapping windows; never mix page/slide boundaries."""
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than chunk size")
    # Merge adjacent segments from the same page so old 1,000-char MVP fragments
    # do not impose arbitrary retrieval boundaries. Paragraph locations stay distinct.
    groups: list[dict] = []
    for segment in segments:
        text = segment["text"].replace("\x00", "").strip()
        if not text:
            continue
        if groups and groups[-1]["location"] == segment["location"]:
            groups[-1]["text"] += "\n" + text
        else:
            groups.append({"text": text, "location": segment["location"]})
    chunks = []
    for segment in groups:
        text = segment["text"]
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                # Prefer a sentence/line boundary; fall back to whitespace.
                cuts = list(re.finditer(r"[.!?]\s|\n|\s", text[start + size // 2 : end]))
                if cuts:
                    end = start + size // 2 + cuts[-1].end()
            if token_count is not None:
                while token_count(text[start:end]) > 400 and end - start > 1:
                    end = start + (end - start) // 2
            value = text[start:end].strip()
            if value:
                chunks.append(
                    {
                        "text": value,
                        "location": segment["location"],
                        "start": start,
                        "end": end,
                        "chunk_index": len(chunks),
                    }
                )
            if end == len(text):
                break
            start = max(start + 1, end - min(overlap, (end - start) // 4))
    return chunks
