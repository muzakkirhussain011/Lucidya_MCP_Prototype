from __future__ import annotations
import re
import logging
from typing import List
from app.domain_models import Company, Person
from app.tools.search import ddg_search

log = logging.getLogger("orchestrator")

# Extract a "Name – Role ..." style from SERP titles
_NAME_RE = re.compile(r"^([A-Za-z][A-Za-z\.\-'\s]{1,60})\s[-|–]\s", re.U)

TITLES = [
    "Head of Customer Experience",
    "Customer Experience Director",
    "Chief Customer Officer",
    "VP Customer Experience",
    "CX Lead",
]

def _slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "contact"

def _guess_email(name: str, domain: str) -> str:
    parts = re.sub(r"[^A-Za-z\s]", "", name).strip().split()
    if not parts:
        return f"info@{domain}"
    first = parts[0].lower()
    last = parts[-1].lower() if len(parts) > 1 else "team"
    return f"{first}.{last}@{domain}"

def _infer_seniority(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["chief ", "cxo", "cmo", "ceo", "coo", "cdo", "cto", "president"]):
        return "executive"
    if "svp" in t or "senior vice president" in t:
        return "svp"
    if "evp" in t:
        return "evp"
    if "vp" in t and "svp" not in t:
        return "vp"
    if "director" in t:
        return "director"
    if "head" in t:
        return "head"
    if "lead" in t:
        return "lead"
    if "manager" in t:
        return "manager"
    if "senior" in t:
        return "senior"
    return "staff"

def _person_id(company: Company, name: str, idx: int) -> str:
    return f"{company.id}-p{idx}-{_slug(name)}"

class PeopleFinderAgent:
    def suggest(self, company: Company, online: bool = False) -> List[Person]:
        # Mock path (ONLY when websearch is OFF)
        if not online:
            log.info("people: using mock contacts for %s", company.name)
            mocks = [
                ("CX Director", "Director, Customer Experience"),
                ("Head of Support", "Head of Support"),
            ]
            out: List[Person] = []
            for i, (name, role) in enumerate(mocks, start=1):
                out.append(
                    Person(
                        id=_person_id(company, name, i),
                        name=name,
                        role=role,
                        email=_guess_email(name, company.domain),
                        seniority=_infer_seniority(role),
                    )
                )
            return out

        # Live websearch path (STRICT: no mock)
        log.info("people: websearch for %s", company.name)
        quoted_titles = '" OR "'.join(TITLES)
        query = f'site:linkedin.com ("{quoted_titles}") {company.name}'
        hits = ddg_search(query, max_results=8)

        people: List[Person] = []
        seen = set()
        i = 0
        for h in hits:
            title = h.get("title") or ""
            m = _NAME_RE.match(title)
            if not m:
                continue
            name = m.group(1).strip()
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            i += 1
            role = "CX leadership (from SERP title)"
            people.append(
                Person(
                    id=_person_id(company, name, i),
                    name=name,
                    role=role,
                    email=_guess_email(name, company.domain),
                    seniority=_infer_seniority(f"{name} {role}"),
                )
            )
            if len(people) >= 3:
                break

        if not people:
            name = "Customer Experience Team"
            people = [
                Person(
                    id=_person_id(company, name, 1),
                    name=name,
                    role="CX Team",
                    email=f"cx@{company.domain}",
                    seniority="team",
                )
            ]

        log.info("people: found=%d", len(people))
        return people