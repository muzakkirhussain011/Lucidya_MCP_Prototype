# file: mcp/servers/calendar_server.py
#!/usr/bin/env python3
import json
from datetime import datetime, timedelta
from aiohttp import web

class CalendarServer:
    """Calendar MCP server"""
    
    async def handle_rpc(self, request):
        data = await request.json()
        method = data.get("method")
        params = data.get("params", {})
        
        if method == "health":
            return web.json_response({"result": "ok"})
        
        elif method == "calendar.suggest_slots":
            # Generate slots for next week
            now = datetime.utcnow()
            slots = []
            
            for days in [2, 3, 5]:  # 2, 3, 5 days from now
                slot_time = now + timedelta(days=days, hours=14)  # 2 PM
                slots.append({
                    "start_iso": slot_time.isoformat(),
                    "end_iso": (slot_time + timedelta(minutes=30)).isoformat()
                })
            
            return web.json_response({"result": slots})
        
        elif method == "calendar.generate_ics":
            summary = params["summary"]
            start = params["start_iso"]
            end = params["end_iso"]
            
            ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Lucidya//MCP//EN
BEGIN:VEVENT
SUMMARY:{summary}
DTSTART:{start.replace('-', '').replace(':', '').replace('.', '')}
DTEND:{end.replace('-', '').replace(':', '').replace('.', '')}
DESCRIPTION:Discuss customer experience improvements
END:VEVENT
END:VCALENDAR"""
            
            return web.json_response({"result": ics})
        
        return web.json_response({"error": "Unknown method"}, status=400)

app = web.Application()
server = CalendarServer()
app.router.add_post("/rpc", server.handle_rpc)

if __name__ == "__main__":
    web.run_app(app, port=9003)