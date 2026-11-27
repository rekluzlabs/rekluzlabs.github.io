"""Bounded retrieval of official Gemini documentation. No downloaded code is run."""
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import URLError

MAX_BYTES = 2_000_000
URLS = {
    "models": "https://aistudio.google.com/docs/models.md",
    "pricing": "https://aistudio.google.com/docs/pricing.md",
    "deprecations": "https://aistudio.google.com/docs/deprecations.md",
    "changelog": "https://aistudio.google.com/docs/changelog.md",
    "migration": "https://aistudio.google.com/docs/migrate-to-interactions",
}


def approved(url):
    p = urlsplit(url)
    return (p.scheme == "https" and p.hostname in {"ai.google.dev", "aistudio.google.com"}
            and p.port is None and not p.username and not p.password and not p.query
            and (p.path.startswith("/docs/") or p.path.startswith("/gemini-api/docs/")))


class LimitedRedirects(HTTPRedirectHandler):
    def __init__(self):
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 3 or not approved(newurl):
            raise ValueError("unapproved documentation redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    if not approved(url):
        raise ValueError("unapproved documentation URL")
    opener = build_opener(LimitedRedirects())
    request = Request(url, headers={"User-Agent": "VaultCuisineAdvisoryMonitor/1.0", "Accept": "text/markdown,text/plain"})
    with opener.open(request, timeout=12) as response:
        if not approved(response.url):
            raise ValueError("unapproved final documentation URL")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("documentation too large")
        content = raw.decode("utf-8", errors="strict")
        if len(content) < 100 or len(content.splitlines()) > 100_000:
            raise ValueError("empty or oversized documentation")
        return content, response.url
