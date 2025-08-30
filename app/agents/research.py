# app/agents/research.py
from __future__ import annotations
import logging
from typing import List, Dict
from urllib.parse import urlparse

from app.domain_models import Company
from app.tools.search import ddg_search
from app.tools.fetch import http_get_text
from app.tools.embeddings import ollama_embed
from app.services.vectorstore import VectorStore

log = logging.getLogger("orchestrator")

class ResearchAgent:
    """
    Discovers pages about a company, fetches & chunks text, embeds, and writes to the vector store.
    """
    def __init__(self, vs: VectorStore):
        self.vs = vs

    def ingest_company_context(self, company: Company, online: bool = True) -> int:
        """Search + fetch + embed. Returns number of chunks stored."""
        queries = [
            f"site:{company.domain} customer experience",
            f"{company.name} reviews NPS",
            f"{company.name} support channels",
        ]

        texts: List[str] = []
        urls:  List[str] = []

        for q in queries:
            log.info("research.search q=%r", q)
            hits = ddg_search(q, max_results=5) if online else []
            log.info("research.search hits=%d", len(hits))
            for h in hits:
                url = h.get("href") or ""
                if not url:
                    continue
                host = urlparse(url).hostname or ""
                log.info("research.fetch url=%s host=%s", url, host)
                body = http_get_text(url)
                if not body:
                    continue
                # chunk up to ~3k chars (6 x 500) to stay cheap with small models
                for i in range(0, min(len(body), 3000), 500):
                    texts.append(body[i:i+500]); urls.append(url)

        if not texts:
            log.warning("research.ingest: no text gathered for %s", company.name)
            return 0

        vecs = ollama_embed(texts)
        for txt, u, v in zip(texts, urls, vecs):
            self.vs.upsert(company.domain, u, txt, v)
        log.info("research.ingest stored=%d", len(texts))
        return len(texts)

    def retrieve(self, company: Company, question: str, top_k: int = 5) -> List[Dict]:
        qv = ollama_embed([question])[0]
        hits = self.vs.search(company.domain, qv, top_k=top_k)
        log.info("research.retrieve k=%d -> hits=%d", top_k, len(hits))
        return hits
