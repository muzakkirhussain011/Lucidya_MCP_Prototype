# file: mcp/servers/email_server.py
#!/usr/bin/env python3
import json
import uuid
from datetime import datetime
from aiohttp import web

class EmailServer:
    """Email MCP server"""
    
    def __init__(self):
        self.threads = {}
        self.messages = []
    
    async def handle_rpc(self, request):
        data = await request.json()
        method = data.get("method")
        params = data.get("params", {})
        
        if method == "health":
            return web.json_response({"result": "ok"})
        
        elif method == "email.send":
            # Create message
            thread_id = str(uuid.uuid4())
            message_id = str(uuid.uuid4())
            
            message = {
                "id": message_id,
                "thread_id": thread_id,
                "prospect_id": params.get("prospect_id", "unknown"),
                "direction": "outbound",
                "to": params["to"],
                "subject": params["subject"],
                "body": params["body"],
                "sent_at": datetime.utcnow().isoformat()
            }
            
            self.messages.append(message)
            
            if thread_id not in self.threads:
                self.threads[thread_id] = []
            self.threads[thread_id].append(message)
            
            return web.json_response({
                "result": {
                    "thread_id": thread_id,
                    "message_id": message_id
                }
            })
        
        elif method == "email.thread":
            prospect_id = params.get("prospect_id")
            
            # Find thread for prospect
            prospect_messages = [
                m for m in self.messages 
                if m.get("prospect_id") == prospect_id
            ]
            
            if prospect_messages:
                thread_id = prospect_messages[0]["thread_id"]
                return web.json_response({
                    "result": {
                        "id": thread_id,
                        "prospect_id": prospect_id,
                        "messages": prospect_messages
                    }
                })
            
            return web.json_response({"result": None})
        
        return web.json_response({"error": "Unknown method"}, status=400)

app = web.Application()
server = EmailServer()
app.router.add_post("/rpc", server.handle_rpc)

if __name__ == "__main__":
    web.run_app(app, port=9002)