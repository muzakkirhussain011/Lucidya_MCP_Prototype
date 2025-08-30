# file: mcp/servers/search_server.py
#!/usr/bin/env python3
import json
from datetime import datetime
from aiohttp import web

class SearchServer:
    """Mock search MCP server"""
    
    async def handle_rpc(self, request):
        data = await request.json()
        method = data.get("method")
        params = data.get("params", {})
        
        if method == "health":
            return web.json_response({"result": "ok"})
        
        elif method == "search.query":
            q = params.get("q", "")
            
            # Mock search results
            results = [
                {
                    "text": f"Found that {q} is a critical priority for modern businesses",
                    "source": "Industry Report 2024",
                    "ts": datetime.utcnow().isoformat(),
                    "confidence": 0.85
                },
                {
                    "text": f"Best practices for {q} include automation and personalization",
                    "source": "CX Weekly",
                    "ts": datetime.utcnow().isoformat(),
                    "confidence": 0.75
                }
            ]
            
            return web.json_response({"result": results})
        
        return web.json_response({"error": "Unknown method"}, status=400)

app = web.Application()
server = SearchServer()
app.router.add_post("/rpc", server.handle_rpc)

if __name__ == "__main__":
    web.run_app(app, port=9001)