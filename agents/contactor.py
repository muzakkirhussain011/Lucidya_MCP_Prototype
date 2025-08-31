# file: agents/contactor.py
from email_validator import validate_email, EmailNotValidError
from app.schema import Prospect, Contact
import uuid
import re

class Contactor:
    """Generates and validates contacts with deduplication"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Generate decision-maker contacts"""
        
        # Check suppression first
        suppressed = await self.store.check_suppression(
            "domain", 
            prospect.company.domain
        )
        
        if suppressed:
            prospect.status = "dropped"
            prospect.dropped_reason = f"Domain suppressed: {prospect.company.domain}"
            await self.store.save_prospect(prospect)
            return prospect
        
        # Generate contacts based on company size
        titles = []
        if prospect.company.size < 100:
            titles = ["CEO", "Head of Customer Success"]
        elif prospect.company.size < 1000:
            titles = ["VP Customer Experience", "Director of CX"]
        else:
            titles = ["Chief Customer Officer", "SVP Customer Success", "VP CX Analytics"]
        
        contacts = []
        seen_emails = set()
        
        # Get existing contacts to dedupe
        existing = await self.store.list_contacts_by_domain(prospect.company.domain)
        for contact in existing:
            seen_emails.add(contact.email.lower())
        
        # Mock names per title to avoid placeholders
        name_pool = {
            "CEO": ["Emma Johnson", "Michael Chen", "Ava Thompson", "Liam Garcia"],
            "Head of Customer Success": ["Daniel Kim", "Priya Singh", "Ethan Brown", "Maya Davis"],
            "VP Customer Experience": ["Olivia Martinez", "Noah Patel", "Sophia Lee", "Jackson Rivera"],
            "Director of CX": ["Henry Walker", "Isabella Nguyen", "Lucas Adams", "Chloe Wilson"],
            "Chief Customer Officer": ["Amelia Clark", "James Wright", "Mila Turner", "Benjamin Scott"],
            "SVP Customer Success": ["Charlotte King", "William Brooks", "Zoe Parker", "Logan Hughes"],
            "VP CX Analytics": ["Harper Bell", "Elijah Foster", "Layla Reed", "Oliver Evans"],
        }

        def pick_name(title: str) -> str:
            pool = name_pool.get(title, ["Alex Morgan"])  # fallback
            # Stable index by company id + title
            key = f"{prospect.company.id}:{title}"
            idx = sum(ord(c) for c in key) % len(pool)
            return pool[idx]

        def email_from_name(name: str, domain: str) -> str:
            parts = re.sub(r"[^a-zA-Z\s]", "", name).strip().lower().split()
            if len(parts) >= 2:
                prefix = f"{parts[0]}.{parts[-1]}"
            else:
                prefix = parts[0]
            email = f"{prefix}@{domain}"
            try:
                return validate_email(email, check_deliverability=False).normalized
            except EmailNotValidError:
                return f"contact@{domain}"

        for title in titles:
            # Create mock contact
            full_name = pick_name(title)
            email = email_from_name(full_name, prospect.company.domain)
            
            # Dedupe
            if email.lower() in seen_emails:
                continue
            
            contact = Contact(
                id=str(uuid.uuid4()),
                name=full_name,
                email=email,
                title=title,
                prospect_id=prospect.id,
            )
            
            contacts.append(contact)
            seen_emails.add(email.lower())
            await self.store.save_contact(contact)
        
        prospect.contacts = contacts
        prospect.status = "contacted"
        await self.store.save_prospect(prospect)
        
        return prospect
