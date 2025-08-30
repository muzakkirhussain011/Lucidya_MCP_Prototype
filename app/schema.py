# file: app/schema.py
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

class Company(BaseModel):
    id: str
    name: str
    domain: str
    industry: str
    size: int
    pains: List[str] = []
    notes: List[str] = []

class Contact(BaseModel):
    id: str
    name: str
    email: EmailStr
    title: str
    prospect_id: str

class Fact(BaseModel):
    id: str
    source: str
    text: str
    collected_at: datetime
    ttl_hours: int
    confidence: float
    company_id: str

class Prospect(BaseModel):
    id: str
    company: Company
    contacts: List[Contact] = []
    facts: List[Fact] = []
    fit_score: float = 0.0
    status: str = "new"  # new, enriched, scored, drafted, compliant, sequenced, ready_for_handoff, dropped
    dropped_reason: Optional[str] = None
    summary: Optional[str] = None
    email_draft: Optional[Dict[str, str]] = None
    thread_id: Optional[str] = None

class Message(BaseModel):
    id: str
    thread_id: str
    prospect_id: str
    direction: str  # outbound, inbound
    subject: str
    body: str
    sent_at: datetime

class Thread(BaseModel):
    id: str
    prospect_id: str
    messages: List[Message] = []

class Suppression(BaseModel):
    id: str
    type: str  # email, domain, company
    value: str
    reason: str
    expires_at: Optional[datetime] = None

class HandoffPacket(BaseModel):
    prospect: Prospect
    thread: Optional[Thread]
    calendar_slots: List[Dict[str, str]] = []
    generated_at: datetime

class PipelineEvent(BaseModel):
    ts: datetime
    type: str  # agent_start, agent_log, agent_end, llm_token, llm_done, policy_block, policy_pass
    agent: str
    message: str
    payload: Dict[str, Any] = {}

class PipelineRequest(BaseModel):
    company_ids: Optional[List[str]] = None

class WriterStreamRequest(BaseModel):
    company_id: str