# file: agents/compliance.py
from pathlib import Path
from app.schema import Prospect
from app.config import (
    COMPANY_FOOTER_PATH, ENABLE_CAN_SPAM, 
    ENABLE_PECR, ENABLE_CASL
)

class Compliance:
    """Enforces email compliance and policies"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
        
        # Load footer
        footer_path = Path(COMPANY_FOOTER_PATH)
        if footer_path.exists():
            self.footer = footer_path.read_text()
        else:
            self.footer = "\n\n---\nLucidya Inc.\n123 Market St, San Francisco, CA 94105\nUnsubscribe: https://lucidya.example.com/unsubscribe"
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Check compliance and enforce policies"""
        
        if not prospect.email_draft:
            prospect.status = "blocked"
            prospect.dropped_reason = "No email draft to check"
            await self.store.save_prospect(prospect)
            return prospect
        
        policy_failures = []
        
        # Check suppression
        for contact in prospect.contacts:
            if await self.store.check_suppression("email", contact.email):
                policy_failures.append(f"Email suppressed: {contact.email}")
            
            domain = contact.email.split("@")[1]
            if await self.store.check_suppression("domain", domain):
                policy_failures.append(f"Domain suppressed: {domain}")
        
        if await self.store.check_suppression("company", prospect.company.id):
            policy_failures.append(f"Company suppressed: {prospect.company.name}")
        
        # Check content requirements
        body = prospect.email_draft.get("body", "")
        
        # CAN-SPAM requirements
        if ENABLE_CAN_SPAM:
            if "unsubscribe" not in body.lower() and "unsubscribe" not in self.footer.lower():
                policy_failures.append("CAN-SPAM: Missing unsubscribe mechanism")
            
            if not any(addr in self.footer for addr in ["St", "Ave", "Rd", "Blvd"]):
                policy_failures.append("CAN-SPAM: Missing physical postal address")
        
        # PECR requirements (UK)
        if ENABLE_PECR:
            # Check for soft opt-in or existing relationship
            # In production, would check CRM for prior relationship
            if "existing customer" not in body.lower():
                # For demo, we'll be lenient
                pass
        
        # CASL requirements (Canada)
        if ENABLE_CASL:
            if "consent" not in body.lower() and prospect.company.domain.endswith(".ca"):
                policy_failures.append("CASL: May need express consent for Canadian recipients")
        
        # Check for unverifiable claims
        forbidden_phrases = [
            "guaranteed", "100%", "no risk", "best in the world",
            "revolutionary", "breakthrough"
        ]
        
        for phrase in forbidden_phrases:
            if phrase in body.lower():
                policy_failures.append(f"Unverifiable claim: '{phrase}'")
        
        # Append footer to email
        if not policy_failures:
            prospect.email_draft["body"] = body + "\n" + self.footer
        
        # Final decision
        if policy_failures:
            prospect.status = "blocked"
            prospect.dropped_reason = "; ".join(policy_failures)
        else:
            prospect.status = "compliant"
        
        await self.store.save_prospect(prospect)
        return prospect