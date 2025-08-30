from __future__ import annotations
from datetime import datetime
from typing import Dict
from app.domain_models import Thread

class MiniCRM:
    def __init__(self):
        self.threads: Dict[str, Thread] = {}
        self.sent_at: Dict[str, datetime] = {}
        self.suppressions: set[str] = set()

    def thread_for(self, company_id: str, person_id: str) -> Thread:
        tid = f"th-{company_id}-{person_id}"
        t = self.threads.get(tid)
        if not t:
            t = Thread(id=tid, company_id=company_id, person_id=person_id)
            self.threads[tid] = t
        return t

    def record_send(self, email: str): self.sent_at[email.lower()] = datetime.utcnow()
    def last_sent(self, email: str):    return self.sent_at.get(email.lower())
    def suppress(self, email: str):      self.suppressions.add(email.lower())
    def unsuppress(self, email: str):    self.suppressions.discard(email.lower())
    def is_suppressed(self, email: str) -> bool: return email.lower() in self.suppressions
