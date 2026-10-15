import json
import socket

import httpx
import pytest

from notebook_ai.extraction import ExtractionError, parse_pptx
from notebook_ai.providers import AIError, GroqProvider
from notebook_ai.urls import extract_page, fetch_page, public_target


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://user:pass@example.com",
        "http://127.0.0.1",
        "http://[::1]",
        "http://169.254.169.254",
        "http://example.com:8080",
    ],
)
def test_unsafe_urls_rejected(url):
    with pytest.raises(ExtractionError):
        public_target(url)


def test_dns_mixed_private_answer_is_rejected(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
        ],
    )
    with pytest.raises(ExtractionError):
        public_target("https://example.com")


def test_single_page_extraction_removes_boilerplate():
    parsed = extract_page(
        b"<title>Study</title><script>secret</script><nav>menu</nav><main><h1>Plants</h1><p>Plants use sunlight.</p></main>",
        "text/html",
    )
    assert "secret" not in parsed["text"] and "menu" not in parsed["text"]
    assert parsed["segments"][1]["location"] == "Paragraph 2"
    assert parsed["title"] == "Study"


def test_bad_pptx_is_a_validation_error():
    with pytest.raises(ExtractionError):
        parse_pptx(b"not a zip file")


def test_redirect_to_private_network_is_revalidated(monkeypatch):
    from notebook_ai import urls

    calls = []

    def resolve(host, *args, **kwargs):
        calls.append(host)
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1" if host == "internal.example" else "93.184.216.34", 443),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolve)

    class Response:
        status = 302

        def getheader(self, name, default=None):
            return "https://internal.example/private" if name == "Location" else default

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(urls.http.client, "HTTPSConnection", Connection)
    with pytest.raises(ExtractionError):
        fetch_page("https://example.com")
    assert calls == ["example.com", "internal.example"]


def test_groq_uses_chosen_model_and_validates_output(monkeypatch):
    from notebook_ai import providers

    real_client = httpx.Client

    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "openai/gpt-oss-20b"
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert "untrusted" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "insufficient_evidence": False,
                                    "claims": [
                                        {"text": "Plants need light.", "citations": ["chunk-1"]}
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(
        providers.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    result = GroqProvider("test-only").generate(
        "plants", [{"id": "chunk-1", "text": "Plants need light."}]
    )
    assert result.claims[0].citations == ["chunk-1"]


def test_missing_key_and_rate_limit_are_explicit(monkeypatch):
    with pytest.raises(AIError, match="GROQ_API_KEY"):
        GroqProvider("").generate("question", [])
    from notebook_ai import providers

    real_client = httpx.Client
    monkeypatch.setattr(
        providers.httpx,
        "Client",
        lambda **kw: real_client(
            transport=httpx.MockTransport(lambda request: httpx.Response(429))
        ),
    )
    with pytest.raises(AIError, match="HTTP 429"):
        GroqProvider("test-only").generate("question", [])


def test_groq_reranker_orders_scores_and_rejects_duplicate_ids(monkeypatch):
    from notebook_ai.providers import RankingDraft

    provider = GroqProvider("test-only")
    monkeypatch.setattr(
        provider,
        "structured",
        lambda *args: RankingDraft.model_validate(
            {"scores": [{"id": "a", "score": 10}, {"id": "b", "score": 90}]}
        ),
    )
    evidence = [{"id": "a", "text": "Distractor"}, {"id": "b", "text": "Answer"}]
    assert provider.rerank("question", evidence) == ["b", "a"]
    monkeypatch.setattr(
        provider,
        "structured",
        lambda *args: RankingDraft.model_validate(
            {"scores": [{"id": "a", "score": 10}, {"id": "a", "score": 90}]}
        ),
    )
    with pytest.raises(AIError, match="invalid passage IDs"):
        provider.rerank("question", evidence)
