# file: agents/curator.py
from datetime import datetime
from app.schema import Prospect, HandoffPacket

class Curator:
    """Creates handoff packets for sales team"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
        self.email_client = mcp_registry.get_email_client()
        self.calendar_client = mcp_registry.get_calendar_client()
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Create handoff packet"""
        
        # Get thread
        thread = None
        if prospect.thread_id:
            thread = await self.email_client.get_thread(prospect.id)
        
        # Get calendar slots
        slots = await self.calendar_client.suggest_slots()
        
        # Create packet
        packet = HandoffPacket(
            prospect=prospect,
            thread=thread,
            calendar_slots=slots,
            generated_at=datetime.utcnow()
        )
        
        # Save packet
        await self.store.save_handoff(packet)
        
        # Update prospect status
        prospect.status = "ready_for_handoff"
        await self.store.save_prospect(prospect)
        
        return prospect