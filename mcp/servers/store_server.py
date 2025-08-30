# file: mcp/servers/store_server.py
#!/usr/bin/env python3
import json
import os
from pathlib import Path
from datetime import datetime
from aiohttp import web
import asyncio

class StoreServer:
    """Store MCP server with JSON persistence"""
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent.parent / "data"
        self.data_dir.mkdir(exist_ok=True)
        
        self.prospects_file = self.data_dir / "prospects.json"
        self.companies_file = self.data_dir / "companies_store.json"
        self.facts_file = self.data_dir / "facts.json"
        self.contacts_file = self.data_dir / "contacts.json"
        self.handoffs_file = self.data_dir / "handoffs.json"
        
        self.lock = asyncio.Lock()
        self._load_data()
    
    def _load_data(self):
        """Load data from files"""
        self.prospects = self._load_json(self.prospects_file, [])
        self.companies = self._load_json(self.companies_file, [])
        self.facts = self._load_json(self.facts_file, [])
        self.contacts = self._load_json(self.contacts_file, [])
        self.handoffs = self._load_json(self.handoffs_file, [])
        
        # Load suppressions
        supp_file = self.data_dir / "suppression.json"
        self.suppressions = self._load_json(supp_file, [])
    
    def _load_json(self, path, default):
        """Load JSON file safely"""
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except:
                pass
        return default
    
    def _save_json(self, path, data):
        """Save JSON file"""
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    async def handle_rpc(self, request):
        data = await request.json()
        method = data.get("method")
        params = data.get("params", {})
        
        if method == "health":
            return web.json_response({"result": "ok"})
        
        async with self.lock:
            if method == "store.save_prospect":
                prospect = params["prospect"]
                # Update or add
                found = False
                for i, p in enumerate(self.prospects):
                    if p["id"] == prospect["id"]:
                        self.prospects[i] = prospect
                        found = True
                        break
                if not found:
                    self.prospects.append(prospect)
                
                self._save_json(self.prospects_file, self.prospects)
                return web.json_response({"result": "saved"})
            
            elif method == "store.get_prospect":
                prospect_id = params["id"]
                for p in self.prospects:
                    if p["id"] == prospect_id:
                        return web.json_response({"result": p})
                return web.json_response({"result": None})
            
            elif method == "store.list_prospects":
                return web.json_response({"result": self.prospects})
            
            elif method == "store.save_company":
                company = params["company"]
                found = False
                for i, c in enumerate(self.companies):
                    if c["id"] == company["id"]:
                        self.companies[i] = company
                        found = True
                        break
                if not found:
                    self.companies.append(company)
                
                self._save_json(self.companies_file, self.companies)
                return web.json_response({"result": "saved"})
            
            elif method == "store.get_company":
                company_id = params["id"]
                for c in self.companies:
                    if c["id"] == company_id:
                        return web.json_response({"result": c})
                
                # Check seed file
                seed_file = self.data_dir / "companies.json"
                if seed_file.exists():
                    with open(seed_file) as f:
                        seeds = json.load(f)
                    for c in seeds:
                        if c["id"] == company_id:
                            return web.json_response({"result": c})
                
                return web.json_response({"result": None})
            
            elif method == "store.save_fact":
                fact = params["fact"]
                self.facts.append(fact)
                self._save_json(self.facts_file, self.facts)
                return web.json_response({"result": "saved"})
            
            elif method == "store.save_contact":
                contact = params["contact"]
                self.contacts.append(contact)
                self._save_json(self.contacts_file, self.contacts)
                return web.json_response({"result": "saved"})
            
            elif method == "store.list_contacts_by_domain":
                domain = params["domain"]
                results = [
                    c for c in self.contacts
                    if c["email"].endswith(f"@{domain}")
                ]
                return web.json_response({"result": results})
            
            elif method == "store.check_suppression":
                supp_type = params["type"]
                value = params["value"]
                
                for supp in self.suppressions:
                    if supp["type"] == supp_type and supp["value"] == value:
                        # Check expiry
                        if supp.get("expires_at"):
                            expires = datetime.fromisoformat(supp["expires_at"])
                            if expires < datetime.utcnow():
                                continue
                        return web.json_response({"result": True})
                
                return web.json_response({"result": False})
            
            elif method == "store.save_handoff":
                packet = params["packet"]
                self.handoffs.append(packet)
                self._save_json(self.handoffs_file, self.handoffs)
                return web.json_response({"result": "saved"})
            
            elif method == "store.clear_all":
                self.prospects = []
                self.companies = []
                self.facts = []
                self.contacts = []
                self.handoffs = []
                
                self._save_json(self.prospects_file, [])
                self._save_json(self.companies_file, [])
                self._save_json(self.facts_file, [])
                self._save_json(self.contacts_file, [])
                self._save_json(self.handoffs_file, [])
                
                return web.json_response({"result": "cleared"})
        
        return web.json_response({"error": "Unknown method"}, status=400)

app = web.Application()
server = StoreServer()
app.router.add_post("/rpc", server.handle_rpc)

if __name__ == "__main__":
    web.run_app(app, port=9004)