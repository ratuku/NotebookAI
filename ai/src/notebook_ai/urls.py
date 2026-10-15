import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from notebook_ai.extraction import MAX_TEXT, ExtractionError, text_segments

MAX_BYTES = 5 * 1024 * 1024


def public_target(url: str):
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or len(url) > 2048
            or any(ord(c) < 33 for c in url)
        ):
            raise ValueError()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError()
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(row[4][0] for row in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError()
        return parsed, port, ips[0]
    except (ValueError, OSError) as exc:
        raise ExtractionError(
            "URL must resolve to a public HTTP(S) page on port 80 or 443."
        ) from exc


def fetch_page(url: str) -> tuple[str, bytes, str]:
    # Resolve and validate each redirect, then pin the actual connection to that IP.
    # HTTPSConnection still verifies TLS against the original hostname. No proxies/cookies.
    for _ in range(4):
        parsed, port, ip = public_target(url)
        connection = (
            http.client.HTTPSConnection(
                parsed.hostname, port, timeout=15, context=ssl.create_default_context()
            )
            if parsed.scheme == "https"
            else http.client.HTTPConnection(parsed.hostname, port, timeout=15)
        )
        connection._create_connection = (
            lambda address, timeout=15, source_address=None, ip=ip, port=port: (
                socket.create_connection((ip, port), timeout)
            )
        )
        try:
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.request(
                "GET",
                path,
                headers={
                    "User-Agent": "NotebookAI/0.1",
                    "Accept": "text/html,text/plain",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                target = response.getheader("Location")
                if not target:
                    raise ExtractionError("The page returned a redirect without a destination.")
                url = urljoin(url, target)
                continue
            if response.status != 200:
                raise ExtractionError(f"The page returned HTTP {response.status}.")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ExtractionError("Compressed page responses are not supported.")
            media = response.getheader("Content-Type", "").split(";", 1)[0].lower()
            if media not in {"text/html", "text/plain", "application/xhtml+xml"}:
                raise ExtractionError("The URL must return a single HTML or plain-text page.")
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ExtractionError("The page exceeds 5 MB.")
            return url, data, media
        except (OSError, http.client.HTTPException) as exc:
            raise ExtractionError("Could not fetch the page within the request limits.") from exc
        finally:
            connection.close()
    raise ExtractionError("The URL redirected too many times.")


def extract_page(data: bytes, media: str) -> dict:
    title = "Web page"
    if media == "text/plain":
        text = data.decode("utf-8-sig", errors="replace")
    else:
        soup = BeautifulSoup(data, "html.parser")
        title = soup.title.get_text(" ", strip=True)[:160] if soup.title else title
        for tag in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
            tag.decompose()
        body = soup.find("main") or soup.find("article") or soup.body or soup
        text = body.get_text("\n", strip=True)
    text = text.replace("\x00", "").strip()
    if not text or len(text) > MAX_TEXT:
        raise ExtractionError("The page has no readable text or exceeds 200,000 characters.")
    return {
        "title": title or "Web page",
        "kind": "url",
        "status": "ready",
        "text": text,
        "segments": text_segments(text),
        "media_type": media,
    }
