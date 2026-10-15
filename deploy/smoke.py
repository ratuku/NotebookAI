"""Credential-free deployment smoke test. Run against an AI_MODE=extractive stack."""

import json
import os
from urllib.request import Request, urlopen

base = os.environ.get("APP_URL", "http://localhost:8080")


def api(path, data=None, method=None):
    request = Request(
        base + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urlopen(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


with urlopen(base, timeout=30) as response:
    assert b"Notebook" in response.read()
assert api("/health")["status"] == "ok"
notebook = api("/api/v1/notebooks", {"title": "Container smoke test"})
path = "/api/v1/notebooks/" + notebook["id"]
try:
    source = api(
        path + "/sources/text",
        {"title": "Plants", "text": "Plants use sunlight for photosynthesis."},
    )
    answer = api(
        path + "/questions",
        {
            "question": "How do plants use sunlight?",
            "source_ids": [source["id"]],
            "retrieval_method": "normal",
        },
    )
    assert answer["citations"] and answer["retrieval_method"] == "normal"
    assert api(path + "/artifacts") == []
    assert len(api(path + "/questions")) == 1
finally:
    api(path, method="DELETE")
print(
    "Container smoke passed: UI, proxy, PostgreSQL, source upload, question, history and cleanup."
)
