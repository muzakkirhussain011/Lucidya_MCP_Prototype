from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class CompanyOut(BaseModel):
    id: str; name: str; domain: str; industry: str
    size: int; region: str; website: str
    challenges: List[str] = []; tech_stack: List[str] = []
    class Config: from_attributes = True

class PersonOut(BaseModel):
    id: str; name: str; role: str; seniority: str
    email: EmailStr; linkedin: Optional[str] = None
    class Config: from_attributes = True

class EmailMessageOut(BaseModel):
    msg_id: str; thread_id: str; sent_at: datetime
    sender: str; recipient: EmailStr; subject: str; body: str
    class Config: from_attributes = True

class ThreadOut(BaseModel):
    id: str; company_id: str; person_id: str
    messages: List[EmailMessageOut] = []
    class Config: from_attributes = True

class HandoffPacket(BaseModel):
    generated_at: datetime
    company: CompanyOut
    internal_summary: str
    thread: ThreadOut

class SuppressIn(BaseModel):
    email: EmailStr

class UnsuppressIn(BaseModel):
    email: EmailStr

class RunFullOut(BaseModel):
    companies_processed: int
    emails_sent: int

class OutreachPreviewItem(BaseModel):
    person: PersonOut
    subject: str
    body: str
    compliance_ok: bool
    reason: str
    class Config: from_attributes = True
