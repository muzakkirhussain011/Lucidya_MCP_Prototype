from __future__ import annotations
from typing import List, Dict
from app.domain_models import Company
from app.tools.llm import _deglue_text

def normalize_bullets(md: str) -> str:
    lines = [ln.rstrip() for ln in (md or "").splitlines()]
    out = []
    for ln in lines:
        if not ln:
            continue
        if not ln.lstrip().startswith("- "):
            # ensure each line is a bullet
            ln = "- " + ln.lstrip("- ").strip()
        out.append(ln)
    return "\n".join(out).strip()

class CompanyEnrichmentAgent:
    def synthesize(self, company: Company, hits: List[Dict]) -> str:
        header = f"Company: {company.name} (industry: {company.industry}, region: {company.region})"
        ctx_lines = []
        for h in hits or []:
            url = h.get("url") or h.get("href") or ""
            text = (h.get("text") or h.get("content") or h.get("body") or "")[:400]
            score = h.get("score")
            if score is not None:
                ctx_lines.append(f"- [{score:.2f}] {text} ({url})")
            else:
                ctx_lines.append(f"- {text} ({url})")
        context = "\n".join(ctx_lines) if ctx_lines else "- (no evidence)"
        out = header + "\nTop evidence (retrieval snippets):\n" + context
        return _deglue_text(out)
