# file: agents/contactor.py
from email_validator import validate_email, EmailNotValidError
from app.schema import Prospect, Contact
import uuid

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
        
        for title in titles:
            # Generate email - Fixed logic to create valid emails
            # Remove special characters and spaces for email prefix
            email_prefix = title.lower().replace(" ", ".").replace("of", "")
            # Remove any remaining special characters
            email_prefix = "".join(c for c in email_prefix if c.isalnum() or c == '.')
            # Ensure it doesn't start or end with a dot
            email_prefix = email_prefix.strip('.')
            # Limit length
            email_prefix = email_prefix[:20]
            
            # Create the email
            email = f"{email_prefix}@{prospect.company.domain}"
            
            # Validate
            try:
                validated = validate_email(email, check_deliverability=False)
                email = validated.normalized
            except EmailNotValidError as e:
                # If validation fails, create a simpler email
                simple_prefix = title.split()[0].lower()
                email = f"{simple_prefix}@{prospect.company.domain}"
                try:
                    validated = validate_email(email, check_deliverability=False)
                    email = validated.normalized
                except:
                    continue
            
            # Dedupe
            if email.lower() in seen_emails:
                continue
            
            contact = Contact(
                id=str(uuid.uuid4()),
                name=f"{title} at {prospect.company.name}",
                email=email,
                title=title,
                prospect_id=prospect.id
            )
            
            contacts.append(contact)
            seen_emails.add(email.lower())
            await self.store.save_contact(contact)
        
        prospect.contacts = contacts
        prospect.status = "contacted"
        await self.store.save_prospect(prospect)
        
        return prospect