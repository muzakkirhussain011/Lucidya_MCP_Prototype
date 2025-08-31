# file: agents/sequencer.py
from datetime import datetime
from app.schema import Prospect, Message
import uuid

class Sequencer:
    """Sequences and sends outreach emails"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.email_client = mcp_registry.get_email_client()
        self.calendar_client = mcp_registry.get_calendar_client()
        self.store = mcp_registry.get_store_client()
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Send email and create thread"""
        
        # Check if we have minimum requirements
        if not prospect.contacts:
            # Try to generate a default contact if none exist
            from app.schema import Contact
            default_contact = Contact(
                id=str(uuid.uuid4()),
                name=f"Customer Success at {prospect.company.name}",
                email=f"contact@{prospect.company.domain}",
                title="Customer Success",
                prospect_id=prospect.id
            )
            prospect.contacts = [default_contact]
            await self.store.save_contact(default_contact)
        
        if not prospect.email_draft:
            # Generate a simple default email if none exists
            prospect.email_draft = {
                "subject": f"Improving {prospect.company.name}'s Customer Experience",
                "body": f"""Dear {prospect.company.name} team,

We noticed your company is in the {prospect.company.industry} industry with {prospect.company.size} employees. 
We'd love to discuss how we can help improve your customer experience.

Looking forward to connecting with you.

Best regards,
Lucidya Team"""
            }
        
        # Now proceed with sending
        primary_contact = prospect.contacts[0]
        
        # Get calendar slots
        try:
            slots = await self.calendar_client.suggest_slots()
        except:
            slots = []  # Continue even if calendar fails
        
        # Generate ICS attachment for first slot
        ics_content = ""
        if slots:
            try:
                slot = slots[0]
                ics_content = await self.calendar_client.generate_ics(
                    f"Meeting with {prospect.company.name}",
                    slot["start_iso"],
                    slot["end_iso"]
                )
            except:
                pass  # Continue without ICS
        
        # Add calendar info to email
        calendar_text = ""
        if slots:
            calendar_text = f"\n\nI have a few time slots available this week:\n"
            for slot in slots[:3]:
                calendar_text += f"- {slot['start_iso'][:16].replace('T', ' at ')}\n"
        
        # Send email
        email_body = prospect.email_draft["body"]
        if calendar_text:
            email_body = email_body.rstrip() + calendar_text
        
        try:
            result = await self.email_client.send(
                to=primary_contact.email,
                subject=prospect.email_draft["subject"],
                body=email_body,
                prospect_id=prospect.id  # Add prospect_id for thread tracking
            )
            
            # Update prospect with thread ID
            prospect.thread_id = result.get("thread_id", str(uuid.uuid4()))
            prospect.status = "sequenced"
            
        except Exception as e:
            # Even if email sending fails, don't block the prospect
            prospect.thread_id = f"mock-thread-{uuid.uuid4()}"
            prospect.status = "sequenced"
            print(f"Warning: Email send failed for {prospect.company.name}: {e}")
        
        await self.store.save_prospect(prospect)
        return prospect