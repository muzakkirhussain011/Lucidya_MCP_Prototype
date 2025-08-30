# file: mcp/registry.py
import asyncio
import aiohttp
from typing import Dict, Any
from app.config import (
    MCP_SEARCH_PORT, MCP_EMAIL_PORT, 
    MCP_CALENDAR_PORT, MCP_STORE_PORT
)

class MCPClient:
    """Base MCP client for server communication"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
    
    async def connect(self):
        """Initialize connection"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close connection"""
        if self.session:
            await self.session.close()
    
    async def call(self, method: str, params: Dict[str, Any] = None):
        """Call MCP method"""
        if not self.session:
            await self.connect()
        
        async with self.session.post(
            f"{self.base_url}/rpc",
            json={"method": method, "params": params or {}}
        ) as response:
            result = await response.json()
            return result.get("result")

class SearchClient(MCPClient):
    """Search MCP client"""
    
    async def query(self, q: str):
        return await self.call("search.query", {"q": q})

class EmailClient(MCPClient):
    """Email MCP client"""
    
    async def send(self, to: str, subject: str, body: str):
        return await self.call("email.send", {
            "to": to, "subject": subject, "body": body
        })
    
    async def get_thread(self, prospect_id: str):
        return await self.call("email.thread", {"prospect_id": prospect_id})

class CalendarClient(MCPClient):
    """Calendar MCP client"""
    
    async def suggest_slots(self):
        return await self.call("calendar.suggest_slots")
    
    async def generate_ics(self, summary: str, start_iso: str, end_iso: str):
        return await self.call("calendar.generate_ics", {
            "summary": summary, 
            "start_iso": start_iso,
            "end_iso": end_iso
        })

class StoreClient(MCPClient):
    """Store MCP client"""
    
    async def save_prospect(self, prospect):
        return await self.call("store.save_prospect", {"prospect": prospect.dict()})
    
    async def get_prospect(self, prospect_id: str):
        result = await self.call("store.get_prospect", {"id": prospect_id})
        if result:
            from app.schema import Prospect
            return Prospect(**result)
    
    async def list_prospects(self):
        results = await self.call("store.list_prospects")
        from app.schema import Prospect
        return [Prospect(**p) for p in results]
    
    async def save_company(self, company):
        return await self.call("store.save_company", {"company": company})
    
    async def get_company(self, company_id: str):
        result = await self.call("store.get_company", {"id": company_id})
        if result:
            from app.schema import Company
            return Company(**result)
    
    async def save_fact(self, fact):
        return await self.call("store.save_fact", {"fact": fact.dict()})
    
    async def save_contact(self, contact):
        return await self.call("store.save_contact", {"contact": contact.dict()})
    
    async def list_contacts_by_domain(self, domain: str):
        results = await self.call("store.list_contacts_by_domain", {"domain": domain})
        from app.schema import Contact
        return [Contact(**c) for c in results]
    
    async def check_suppression(self, type: str, value: str):
        return await self.call("store.check_suppression", {"type": type, "value": value})
    
    async def save_handoff(self, packet):
        return await self.call("store.save_handoff", {"packet": packet.dict()})
    
    async def clear_all(self):
        return await self.call("store.clear_all")

class MCPRegistry:
    """Central registry for all MCP clients"""
    
    def __init__(self):
        self.search = SearchClient(f"http://localhost:{MCP_SEARCH_PORT}")
        self.email = EmailClient(f"http://localhost:{MCP_EMAIL_PORT}")
        self.calendar = CalendarClient(f"http://localhost:{MCP_CALENDAR_PORT}")
        self.store = StoreClient(f"http://localhost:{MCP_STORE_PORT}")
    
    async def connect(self):
        """Connect all clients"""
        await self.search.connect()
        await self.email.connect()
        await self.calendar.connect()
        await self.store.connect()
    
    async def health_check(self):
        """Check health of all MCP servers"""
        status = {}
        
        for name, client in [
            ("search", self.search),
            ("email", self.email),
            ("calendar", self.calendar),
            ("store", self.store)
        ]:
            try:
                await client.call("health")
                status[name] = "healthy"
            except Exception as e:
                status[name] = f"unhealthy: {str(e)}"
        
        return status
    
    def get_search_client(self) -> SearchClient:
        return self.search
    
    def get_email_client(self) -> EmailClient:
        return self.email
    
    def get_calendar_client(self) -> CalendarClient:
        return self.calendar
    
    def get_store_client(self) -> StoreClient:
        return self.store