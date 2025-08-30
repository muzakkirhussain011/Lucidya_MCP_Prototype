from __future__ import annotations
import logging, re
from typing import Optional
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("fetch")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

def _clean_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    # normalize spacing
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def http_get_text(url: str, timeout: int = 25) -> Optional[str]:
    """
    Fetches a URL with a realistic UA and returns readable text content.
    If blocked, tries a plain GET without UA as a fallback (some CDNs).
    """
    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if "text/html" in ctype or "application/xhtml+xml" in ctype:
            return _clean_html(r.text)
        # PDFs or others: return short notice (vector store can still work)
        if "pdf" in ctype:
            return f"[PDF] {url}"
        return r.text[:8000]
    except Exception as e:
        log.warning("fetch failed UA %s: %s", url, e)

    # fallback without UA
    try:
        r = requests.get(url, timeout=timeout)
        r.raise_for_status()
        ctype = (r.headers.get("content-type") or "").lower()
        if "text/html" in ctype or "application/xhtml+xml" in ctype:
            return _clean_html(r.text)
        if "pdf" in ctype:
            return f"[PDF] {url}"
        return r.text[:8000]
    except Exception as e:
        log.warning("fetch failed no-UA %s: %s", url, e)
        return None
