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
        evidence = []  # list of dicts {title, url, snippet}

        if use_online:
            # Clean company name for search (remove parenthetical parts)
            name_key = c.name.split("(")[0].strip()

            queries = [
                f'site:{c.domain} "customer care" OR support OR complaints',
                f'"customer experience" site:{c.domain} OR CX {name_key}',
                f'{name_key} NPS OR "Net Promoter Score" reviews',
                f'site:{c.domain} contact OR "how to reach us" OR channels',
            ]

            for q in queries:
                yield {"type": "search", "query": q}
                try:
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
                        
                        try:
                            body = http_get_text(url)
                            ok = bool(body)
                            chars = len(body or "")
                            yield {"type": "fetch_done", "ok": ok, "chars": chars, "host": host}
                            
                            if body:
                                # Keep bounded chunks for embeddings
                                for i in range(0, min(len(body), 3000), 500):
                                    chunk = body[i:i+500]
                                    if chunk.strip():  # Only add non-empty chunks
                                        texts.append(chunk)
                                        urls.append(url)
                        except Exception as e:
                            log.warning("Fetch failed for %s: %s", url, e)
                            yield {"type": "fetch_done", "ok": False, "chars": 0, "host": host}
                            
                except Exception as e:
                    log.error("Search failed for query %r: %s", q, e)
                    yield {"type": "search_error", "query": q, "error": str(e)}
        else:
            # Mock mode - always provide data
            mocks = _mock_chunks(c)
            yield {"type": "mock_seed", "count": len(mocks)}
            for u, txt in mocks:
                evidence.append({"title": f"Mock: {u}", "url": u})
                for i in range(0, len(txt), 500):
                    chunk = txt[i:i+500]
                    if chunk.strip():
                        texts.append(chunk)
                        urls.append(u)

        # If no content found, provide fallback
        if not texts:
            log.warning("No content found, using fallback for %s", c.name)
            yield {"type": "no_content", "namespace": ns}
            # Provide some basic fallback content
            fallback_text = f"""
            {c.name} is a {c.industry} company in {c.region} with approximately {c.size} employees.
            Their main website is {c.website}. Key challenges in the industry typically include:
            {', '.join(c.challenges[:2]) if c.challenges else 'customer satisfaction and operational efficiency'}.
            """
            texts = [fallback_text]
            urls = [c.website]

        # Persist to vector store
        try:
            vecs = ollama_embed(texts)
            yield {"type": "embedded", "chunks": len(vecs), "namespace": ns}
            for txt, u, v in zip(texts, urls, vecs):
                self.vs.upsert(ns, u, txt, v)
        except Exception as e:
            log.error("Embedding failed: %s", e)
            yield {"type": "embed_error", "error": str(e), "namespace": ns}
            # Continue with empty retrieval

        # Retrieve and summarize
        q = f"Customer experience issues and opportunities for {c.name}"
        try:
            qv = ollama_embed([q])[0]
            hits = self.vs.search(ns, qv, top_k=5)
            yield {"type": "retrieve", "hits": len(hits), "namespace": ns}
        except Exception as e:
            log.error("Retrieval failed: %s", e)
            hits = []
            yield {"type": "retrieve", "hits": 0, "namespace": ns}

        # Build context for summary
        if hits:
            summary_in = self.enrich.synthesize(c, hits)
        else:
            # Provide basic context even without retrieval
            summary_in = f"""
            Company: {c.name}
            Industry: {c.industry}
            Region: {c.region}
            Size: {c.size} employees
            
            Known challenges:
            {chr(10).join('- ' + ch for ch in c.challenges) if c.challenges else '- General CX improvement needed'}
            
            Technology stack:
            {', '.join(c.tech_stack) if c.tech_stack else 'Standard enterprise tools'}
            
            Generate a brief summary of potential CX opportunities for this company.
            """

        yield {"type": "llm_begin", "what": "internal_summary", "format": "markdown"}
        
        buf = []
        try:
            for md_chunk in self.writer.internal_summary_stream(summary_in):
                buf.append(md_chunk)
                yield {"type": "llm_delta", "delta": md_chunk, "format": "markdown"}
        except Exception as e:
            log.error("LLM streaming failed: %s", e)
            yield {"type": "llm_error", "error": str(e)}
            # Provide a basic summary
            buf = [f"- {c.name} could benefit from enhanced CX analytics\n",
                   f"- Opportunity to improve customer satisfaction metrics\n",
                   f"- Potential for automation in support channels\n"]
            for chunk in buf:
                yield {"type": "llm_delta", "delta": chunk, "format": "markdown"}
        
        internal_summary = normalize_bullets("".join(buf))
        yield {"type": "llm_complete", "chars": len(internal_summary)}

        # Emit sources for audit
        if evidence:
            # Dedup by URL and cap to 10
            seen = set()
            srcs = []
            for e in evidence:
                u = e.get("url", "")
                if u and u not in seen:
                    srcs.append(e)
                    seen.add(u)
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

        try:
            contacts = self.people.suggest(c, online=use_online)
            yield {"type": "contacts", "count": len(contacts)}
        except Exception as e:
            log.error("People finder failed: %s", e)
            # Provide fallback contact
            from app.agents.people import _person_id, _guess_email, _infer_seniority
            fallback = Person(
                id=_person_id(c, "Customer Team", 1),
                name="Customer Experience Team",
                role="CX Team",
                email=_guess_email("Customer Team", c.domain),
                seniority="team"
            )
            contacts = [fallback]
            yield {"type": "contacts", "count": 1}

        # Get context for email
        q = f"CX issues for {c.name}"
        try:
            qv = ollama_embed([q])[0]
            hits = self.vs.search(ns, qv, top_k=3)
        except:
            hits = []
            
        for p in contacts:
            ok, why = self.compliance.ok_to_contact(p.email)
            if bypass_compliance:
                ok, why = True, "Bypassed for preview"
            yield {"type": "compose_begin", "person": p.name, "email": p.email, "compliance": ok, "reason": why, "namespace": ns}
            
            if not ok:
                continue
                
            yield {"type": "context_hits", "hits": len(hits)}
            
            body_buf = []
            try:
                for result in self.writer.outreach_stream(c, p):
                    if result[0] == "subject":
                        subject = result[1]
                        yield {"type": "subject", "subject": subject}
                    elif result[0] == "body_delta":
                        delta = result[1]
                        body_buf.append(delta)
                        yield {"type": "llm_delta", "delta": delta, "format": "markdown"}
                    elif result[0] == "final":
                        subject, body = result[1], result[2]
                        yield {"type": "final_email", "subject": subject, "body": body, "person": p.name, "email": p.email}
            except Exception as e:
                log.error("Email composition failed: %s", e)
                yield {"type": "compose_error", "error": str(e)}
                
        yield {"type": "done", "namespace": ns}

    def _get(self, company_id: str) -> Company:
        c = next((x for x in self._companies if x.id == company_id), None)
        if not c:
            raise ValueError("Company not found")
        return c