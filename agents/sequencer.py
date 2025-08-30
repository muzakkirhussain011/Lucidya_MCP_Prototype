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
        
        if not prospect.email_draft or not prospect.contacts:
            prospect.status = "blocked"
            prospect.dropped_reason = "No email draft or contacts"
            await self.store.save_prospect(prospect)
            return prospect
        
        # Send to first contact
        primary_contact = prospect.contacts[0]
        
        # Get calendar slots
        slots = await self.calendar_client.suggest_slots()
        
        # Generate ICS attachment for first slot
        ics_content = ""
        if slots:
            slot = slots[0]
            ics_content = await self.calendar_client.generate_ics(
                f"Meeting with {prospect.company.name}",
                slot["start_iso"],
                slot["end_iso"]
            )
        
        # Add calendar info to email
        calendar_text = ""
        if slots:
            calendar_text = f"\n\nI have a few time slots available this week:\n"
            for slot in slots[:3]:
                calendar_text += f"- {slot['start_iso']}\n"
        
        # Send email
        email_body = prospect.email_draft["body"] + calendar_text
        
        result = await self.email_client.send(
            to=primary_contact.email,
            subject=prospect.email_draft["subject"],
            body=email_body
        )
        
        # Update prospect
        prospect.thread_id = result["thread_id"]
        prospect.status = "sequenced"
        await self.store.save_prospect(prospect)
        
        return prospect