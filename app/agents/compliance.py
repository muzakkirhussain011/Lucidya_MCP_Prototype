from datetime import datetime, timedelta
from app.services.crm import MiniCRM

class ComplianceAgent:
    def __init__(self, crm: MiniCRM, min_days_between: int = 14):
        self.crm = crm; self.min_days = min_days_between

    def ok_to_contact(self, email: str) -> tuple[bool,str]:
        if self.crm.is_suppressed(email): return False, "Suppressed (opt-out)."
        last = self.crm.last_sent(email)
        if last and (datetime.utcnow() - last) < timedelta(days=self.min_days):
            return False, "Recently contacted."
        return True, "OK"

    def lint(self, subject: str, body: str) -> list[str]:
        issues = []
        if not subject.strip(): issues.append("Empty subject.")
        if "unsubscribe" not in body.lower(): issues.append("Missing unsubscribe.")
        if len(body) > 1200: issues.append("Body too long.")
        return issues
