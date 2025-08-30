from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class Company:
    id: str
    name: str
    domain: str
    industry: str
    size: int
    region: str
    website: str
    challenges: List[str] = field(default_factory=list)
    tech_stack: List[str] = field(default_factory=list)
    notes: str = ""
    last_enriched_at: Optional[datetime] = None

@dataclass
class Person:
    id: str
    name: str
    role: str
    seniority: str
    email: str
    linkedin: Optional[str] = None

@dataclass
class EmailMessage:
    msg_id: str
    thread_id: str
    sent_at: datetime
    sender: str
    recipient: str
    subject: str
    body: str

@dataclass
class Thread:
    id: str
    company_id: str
    person_id: str
    messages: List[EmailMessage] = field(default_factory=list)
