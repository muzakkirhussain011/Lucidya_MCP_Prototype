import uuid
from datetime import datetime
from app.domain_models import Company, Person, EmailMessage
from app.services.crm import MiniCRM

class OutreachAgent:
    def __init__(self, crm: MiniCRM, sender_email: str):
        self.crm = crm; self.sender_email = sender_email

    def send(self, company: Company, person: Person, subject: str, body: str):
        t = self.crm.thread_for(company.id, person.id)
        msg = EmailMessage(
            msg_id=uuid.uuid4().hex, thread_id=t.id, sent_at=datetime.utcnow(),
            sender=self.sender_email, recipient=person.email, subject=subject, body=body
        )
        t.messages.append(msg); self.crm.record_send(person.email)
        return t
