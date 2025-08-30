# file: app/main.py
import json
from datetime import datetime
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from app.schema import PipelineRequest, WriterStreamRequest, Prospect, HandoffPacket
from app.orchestrator import Orchestrator
from app.config import OLLAMA_BASE_URL, MODEL_NAME
from app.logging_utils import setup_logging
from mcp.registry import MCPRegistry
from vector.store import VectorStore
import requests

setup_logging()

app = FastAPI(title="Lucidya MCP Prototype", version="0.1.0")
orchestrator = Orchestrator()
mcp = MCPRegistry()
vector_store = VectorStore()

@app.on_event("startup")
async def startup():
    """Initialize connections on startup"""
    await mcp.connect()

@app.get("/health")
async def health():
    """Health check with Ollama connectivity test"""
    try:
        # Check Ollama
        ollama_ok = False
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            ollama_ok = resp.status_code == 200
        except:
            pass
        
        # Check MCP servers
        mcp_status = await mcp.health_check()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "ollama": {
                "connected": ollama_ok,
                "base_url": OLLAMA_BASE_URL,
                "model": MODEL_NAME
            },
            "mcp": mcp_status,
            "vector_store": vector_store.is_initialized()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

async def stream_pipeline(request: PipelineRequest) -> AsyncGenerator[bytes, None]:
    """Stream NDJSON events from pipeline"""
    async for event in orchestrator.run_pipeline(request.company_ids):
        yield (json.dumps(event) + "\n").encode()

@app.post("/run")
async def run_pipeline(request: PipelineRequest):
    """Run the full pipeline with NDJSON streaming"""
    return StreamingResponse(
        stream_pipeline(request),
        media_type="application/x-ndjson"
    )

async def stream_writer_test(company_id: str) -> AsyncGenerator[bytes, None]:
    """Stream only Writer agent output for testing"""
    from agents.writer import Writer
    
    # Get company from store
    store = mcp.get_store_client()
    company = await store.get_company(company_id)
    
    if not company:
        yield (json.dumps({"error": f"Company {company_id} not found"}) + "\n").encode()
        return
    
    # Create a test prospect
    prospect = Prospect(
        id=f"{company_id}_test",
        company=company,
        contacts=[],
        facts=[],
        fit_score=0.8,
        status="scored"
    )
    
    writer = Writer(mcp)
    async for event in writer.run_streaming(prospect):
        yield (json.dumps(event) + "\n").encode()

@app.post("/writer/stream")
async def writer_stream_test(request: WriterStreamRequest):
    """Test endpoint for Writer streaming"""
    return StreamingResponse(
        stream_writer_test(request.company_id),
        media_type="application/x-ndjson"
    )

@app.get("/prospects")
async def list_prospects():
    """List all prospects with status and scores"""
    store = mcp.get_store_client()
    prospects = await store.list_prospects()
    return {
        "count": len(prospects),
        "prospects": [
            {
                "id": p.id,
                "company": p.company.name,
                "status": p.status,
                "fit_score": p.fit_score,
                "contacts": len(p.contacts),
                "facts": len(p.facts)
            }
            for p in prospects
        ]
    }

@app.get("/prospects/{prospect_id}")
async def get_prospect(prospect_id: str):
    """Get detailed prospect information"""
    store = mcp.get_store_client()
    prospect = await store.get_prospect(prospect_id)
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Get thread if exists
    email_client = mcp.get_email_client()
    thread = None
    if prospect.thread_id:
        thread = await email_client.get_thread(prospect.id)
    
    return {
        "prospect": prospect.dict(),
        "thread": thread.dict() if thread else None
    }

@app.get("/handoff/{prospect_id}")
async def get_handoff(prospect_id: str):
    """Get handoff packet for a prospect"""
    store = mcp.get_store_client()
    prospect = await store.get_prospect(prospect_id)
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    if prospect.status != "ready_for_handoff":
        raise HTTPException(status_code=400, 
                          detail=f"Prospect not ready for handoff (status: {prospect.status})")
    
    # Get thread
    email_client = mcp.get_email_client()
    thread = None
    if prospect.thread_id:
        thread = await email_client.get_thread(prospect.id)
    
    # Get calendar slots
    calendar_client = mcp.get_calendar_client()
    slots = await calendar_client.suggest_slots()
    
    packet = HandoffPacket(
        prospect=prospect,
        thread=thread,
        calendar_slots=slots,
        generated_at=datetime.utcnow()
    )
    
    return packet.dict()

@app.post("/reset")
async def reset_system():
    """Clear store, reload seeds, rebuild FAISS"""
    store = mcp.get_store_client()
    
    # Clear all data
    await store.clear_all()
    
    # Reload seed companies
    import json
    from app.config import COMPANIES_FILE
    
    with open(COMPANIES_FILE) as f:
        companies = json.load(f)
    
    for company_data in companies:
        await store.save_company(company_data)
    
    # Rebuild vector index
    vector_store.rebuild_index()
    
    return {
        "status": "reset_complete",
        "companies_loaded": len(companies),
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)