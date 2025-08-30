from __future__ import annotations
import logging, re, time
from typing import List, Dict, Optional, Iterable
from urllib.parse import urlencode

try:
    # Preferred package name
    from ddgs import DDGS  # pip install ddgs
except Exception:  # pragma: no cover
    # Back-compat for older envs
    from duckduckgo_search import DDGS  # deprecated

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("search")

# Detect site:domain usage
_SITE_RE = re.compile(r"\bsite:([a-z0-9\.\-]+)", re.I)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HTML_ENDPOINTS = [
    "https://duckduckgo.com/html/",
    "https://html.duckduckgo.com/html/",
    "https://lite.duckduckgo.com/lite/",
]

def _strip_parens_company(q: str) -> str:
    # "stc (Saudi Telecom Company)" -> "stc"
    return re.sub(r"\s*\([^)]*\)", "", q).strip()

def _extract_site_domain(q: str) -> Optional[str]:
    m = _SITE_RE.search(q or "")
    return m.group(1).lower() if m else None

def _variants(q: str) -> List[str]:
    """
    Progressively looser variants to increase recall:
      - original
      - remove parenthetical aliases
      - 'site domain' phrasing
      - no site: (we'll post-filter)
    """
    q = q.strip()
    base = q
    out = [base]

    no_paren = _strip_parens_company(base)
    if no_paren != base:
        out.append(no_paren)

    dom = _extract_site_domain(base)
    if dom:
        out.append(re.sub(_SITE_RE, f"site {dom}", base))
        out.append(_SITE_RE.sub("", base).strip())

    seen = set()
    uniq: List[str] = []
    for s in out:
        if s and s not in seen:
            uniq.append(s); seen.add(s)
    return uniq

def _filter_by_domain(hits: List[Dict], domain: Optional[str]) -> List[Dict]:
    if not domain:
        return hits
    dom = domain.lower()
    keep = []
    for h in hits:
        href = (h.get("href") or "").lower()
        if dom in href:
            keep.append(h)
    return keep

def _ddg_text_once(client: DDGS, query: str, region: str, safesearch: str,
                   timelimit: Optional[str], max_results: int) -> List[Dict]:
    results: List[Dict] = []
    try:
        gen = client.text(
            keywords=query,
            region=region,
            safesearch=safesearch,
            timelimit=timelimit
        )
        for r in gen:
            if not r:
                continue
            results.append({
                "title": r.get("title") or "",
                "href": r.get("href") or "",
                "body": r.get("body") or "",
            })
            if len(results) >= max_results:
                break
    except Exception as e:
        log.warning("ddg_text failed q=%r region=%s: %s", query, region, e)
    return results

def _ddg_html_scrape(query: str, max_results: int = 10, region_hint: str = "us-en") -> List[Dict]:
    """
    Fallback: scrape DDG HTML / Lite endpoints with a realistic UA.
    """
    params = {"q": query, "kl": region_hint}
    headers = {"User-Agent": UA}
    results: List[Dict] = []
    seen = set()

    for base in HTML_ENDPOINTS:
        url = f"{base}?{urlencode(params)}"
        try:
            log.info("ddg_html GET %s", url)
            r = requests.get(url, headers=headers, timeout=200)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            # Try multiple selector styles (HTML & Lite)
            anchors = soup.select("a.result__a, a.result__url, a[href].result-link, a[href].result__url__link")
            if not anchors:
                # very minimal lite: all anchors inside result table rows
                anchors = [a for a in soup.find_all("a", href=True)]
            for a in anchors:
                href = a.get("href", "")
                if not href.startswith("http"):
                    continue
                title = (a.get_text(" ", strip=True) or "").strip()
                if href in seen:
                    continue
                results.append({"title": title, "href": href, "body": ""})
                seen.add(href)
                if len(results) >= max_results:
                    return results
        except Exception as e:
            log.warning("ddg_html failed %s: %s", url, e)
    return results

def ddg_search(query: str, max_results: int = 6) -> List[Dict]:
    """
    Resilient DuckDuckGo search that:
      • builds variants (strip parentheses, relax site:)
      • tries regions (xa-en → wt-wt → us-en)
      • post-filters by domain when 'site:domain' present
      • falls back to HTML/Lite scraping with real UA if API returns 0
    Returns list of {title, href, body}.
    """
    region_chain = ("xa-en", "wt-wt", "us-en")
    safesearch = "moderate"
    timelimit = None  # 'd','w','m' if you want recency filtering

    variants = _variants(query)
    site_domain = _extract_site_domain(query)

    log.info("ddg_search q=%r variants=%d site_domain=%s", query, len(variants), site_domain or "-")
    out: List[Dict] = []
    seen_href = set()

    try:
        with DDGS() as client:
            for region in region_chain:
                for qv in variants:
                    log.info("ddgs.text q=%r region=%s safe=%s", qv, region, safesearch)
                    batch = _ddg_text_once(client, qv, region, safesearch, timelimit, max_results * 2)
                    if site_domain:
                        batch = _filter_by_domain(batch, site_domain)
                    for h in batch:
                        href = h.get("href") or ""
                        if href and href not in seen_href:
                            out.append(h); seen_href.add(href)
                            if len(out) >= max_results:
                                log.info("ddg_search satisfied with %d hits (API)", len(out))
                                return out
    except Exception as e:
        log.warning("DDGS client init/usage failed: %s", e)

    # Fallback if API yielded nothing
    if not out:
        for qv in variants:
            batch = _ddg_html_scrape(qv, max_results=max_results * 2)
            if site_domain:
                batch = _filter_by_domain(batch, site_domain)
            for h in batch:
                href = h.get("href") or ""
                if href and href not in seen_href:
                    out.append(h); seen_href.add(href)
                    if len(out) >= max_results:
                        log.info("ddg_search satisfied with %d hits (HTML fallback)", len(out))
                        return out

    log.info("ddg_search -> %d hits", len(out))
    return out
