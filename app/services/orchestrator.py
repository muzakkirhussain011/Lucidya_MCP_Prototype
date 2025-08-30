from __future__ import annotations
import logging
from urllib.parse import urlparse

from app.config import get_settings
from app.domain_models import Company
from app.services.crm import MiniCRM
from app.services.vectorstore import VectorStore

from app.agents.planner import PlannerAgent
from app.agents.discovery import DiscoveryAgent
from app.agents.research import ResearchAgent
from app.agents.enrichment import CompanyEnrichmentAgent, normalize_bullets
from app.agents.people import PeopleFinderAgent
from app.agents.writer import WriterAgent
from app.agents.compliance import ComplianceAgent
from app.agents.outreach import OutreachAgent

from app.tools.embeddings import ollama_embed
from app.tools.search import ddg_search
from app.tools.fetch import http_get_text

log = logging.getLogger("orchestrator")

def _mock_chunks(company: Company) -> list[tuple[str, str]]:
    return [
        (f"mock://{company.domain}/cx-overview",
         f"{company.name} has a large, multilingual customer base. Common goals include reducing AHT, improving NPS, and unifying omnichannel analytics."),
        (f"mock://{company.domain}/support-channels",
         f"{company.name} supports Arabic/English channels (app, chat, call center, WhatsApp). Pain points: handoffs, backlog spikes, limited proactive alerts."),
        (f"mock://{company.domain}/stack",
         f"Likely stack includes Salesforce/Genesys/WhatsApp Business API. Opportunities: real-time voice of customer, AI summaries, and intent detection.")
    ]

class Orchestrator:
    def __init__(self, crm: MiniCRM, vs: VectorStore):
        self.settings = get_settings()
        self.crm = crm
        self.vs = vs

        self.planner = PlannerAgent()
        self.discovery = DiscoveryAgent()
        self.research = ResearchAgent(vs)
        self.enrich = CompanyEnrichmentAgent()
        self.people = PeopleFinderAgent()
        self.writer = WriterAgent()
        self.compliance = ComplianceAgent(crm, self.settings.min_days_between_touches)
        self.outreach = OutreachAgent(crm, self.writer.sender_email)

        self._companies: list[Company] = self.discovery.seed()

    def companies(self) -> list[Company]:
        return self._companies

    # ------------ Streaming research with online toggle ------------
    def research_company_events(self, company_id: str, online: bool | None = None):
        c = self._get(company_id)
        use_online = self.settings.online_search if online is None else online
        ns = f"{c.domain}#{'web' if use_online else 'mock'}"
        log.info("events:research:start company=%s id=%s online=%s ns=%s", c.name, c.id, use_online, ns)
        yield {"type": "start", "company": c.name, "id": c.id, "online": use_online, "namespace": ns}

        texts, urls = [], []
        evidence = []  # list of dicts {title, href}

        if use_online:
            # Avoid parentheses poisoning search ("stc (Saudi Telecom Company)" -> "stc")
            name_key = c.name.split("(")[0].strip()

            queries = [
                f'site:{c.domain} "customer care" OR support OR complaints',
                f'"customer experience" site:{c.domain} OR CX {name_key}',
                f'{name_key} NPS OR "Net Promoter Score" reviews',
                f'site:{c.domain} contact OR "how to reach us" OR channels',
            ]

            for q in queries:
                yield {"type": "search", "query": q}
                hits = ddg_search(q, max_results=8)
                yield {"type": "search_results", "count": len(hits)}
                for h in hits:
                    url = h.get("href")
                    title = h.get("title") or ""
                    if not url:
                        continue
                    evidence.append({"title": title, "url": url})
                    host = urlparse(url).hostname or ""
                    yield {"type": "fetch_start", "url": url, "host": host}
                    body = http_get_text(url)
                    yield {"type": "fetch_done", "ok": bool(body), "chars": len(body or ""), "host": host}
                    if not body:
                        continue
                    # keep a bounded sample of content for embeddings
                    for i in range(0, min(len(body), 3000), 500):
                        texts.append(body[i:i+500]); urls.append(url)
        else:
            mocks = _mock_chunks(c)
            yield {"type": "mock_seed", "count": len(mocks)}
            for u, txt in mocks:
                for i in range(0, len(txt), 500):
                    texts.append(txt[i:i+500]); urls.append(u)

        if not texts:
            yield {"type": "no_content", "namespace": ns}
            yield {"type": "done", "internal_summary": "_No content available for summarization._", "namespace": ns}
            return

        # persist to vector store
        vecs = ollama_embed(texts)
        yield {"type": "embedded", "chunks": len(vecs), "namespace": ns}
        for txt, u, v in zip(texts, urls, vecs):
            self.vs.upsert(ns, u, txt, v)

        # retrieve and summarize
        q = f"Customer experience issues and opportunities for {c.name}"
        qv = ollama_embed([q])[0]
        hits = self.vs.search(ns, qv, top_k=5)
        yield {"type": "retrieve", "hits": len(hits), "namespace": ns}

        summary_in = self.enrich.synthesize(c, hits)
        yield {"type": "llm_begin", "what": "internal_summary", "format": "markdown"}
        buf = []
        for md_chunk in self.writer.internal_summary_stream(summary_in):
            buf.append(md_chunk)
            yield {"type": "llm_delta", "delta": md_chunk, "format": "markdown"}
        internal_summary = normalize_bullets("".join(buf))
        yield {"type": "llm_complete", "chars": len(internal_summary)}

        # emit sources so UI can display and user can verify websearch (no mock)
        if evidence:
            # dedup by URL and cap to 10
            seen = set(); srcs = []
            for e in evidence:
                u = e["url"]
                if u not in seen:
                    srcs.append(e); seen.add(u)
                if len(srcs) >= 10:
                    break
            yield {"type": "evidence", "sources": srcs}

        yield {"type": "done", "internal_summary": internal_summary, "namespace": ns}
        log.info("events:research:done company=%s hits=%d", c.name, len(hits))

    def preview_outreach_company_events(self, company_id: str, online: bool | None = None, bypass_compliance: bool = True):
        c = self._get(company_id)
        use_online = self.settings.online_search if online is None else online
        ns = f"{c.domain}#{'web' if use_online else 'mock'}"
        yield {"type": "start", "company": c.name, "id": c.id, "online": use_online, "namespace": ns}

        contacts = self.people.suggest(c, online=use_online)
        yield {"type": "contacts", "count": len(contacts)}
        qv = ollama_embed([f"CX issues for {c.name}"])[0]
        hits = self.vs.search(ns, qv, top_k=3)
        for p in contacts:
            ok, why = self.compliance.ok_to_contact(p.email)
            if bypass_compliance:
                ok, why = True, "Bypassed for preview"
            yield {"type": "compose_begin", "person": p.name, "email": p.email, "compliance": ok, "reason": why, "namespace": ns}
            yield {"type": "context_hits", "hits": len(hits)}
            body_buf = []
            for kind in self.writer.outreach_stream(c, p):
                if kind[0] == "body_delta":
                    body_buf.append(kind[1])
                    yield {"type": "llm_delta", "delta": kind[1], "format": "markdown"}
                else:
                    subject, body = kind[1], kind[2]
                    yield {"type": "final_email", "subject": subject, "body": body, "person": p.name, "email": p.email}
        yield {"type": "done", "namespace": ns}

    def _get(self, company_id: str) -> Company:
        c = next((x for x in self._companies if x.id == company_id), None)
        if not c:
            raise ValueError("Company not found")
        return c
