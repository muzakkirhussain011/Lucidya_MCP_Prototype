from __future__ import annotations
import os, json, logging, sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

# Ensure app modules are importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.logging_config import setup_logging
from app.services.vectorstore import VectorStore
from app.services.crm import MiniCRM
from app.services.orchestrator import Orchestrator
from app.tools.llm import check_llm_ready
from app.tools.embeddings import check_embeddings_ready

# Setup logging
setup_logging()
log = logging.getLogger("uvicorn.error")

app = FastAPI(title="Lucidya Demo API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

settings = get_settings()
vs = VectorStore()
crm = MiniCRM()
orch = Orchestrator(crm, vs)

@app.on_event("startup")
async def startup_event():
    """Check system readiness at startup."""
    llm_ok = False
    embed_ok = False
    
    if settings.require_llm:
        llm_ok = check_llm_ready()
        if not llm_ok:
            log.warning("LLM not ready at startup - will work in mock mode only")
    
    if settings.require_embeddings:
        embed_ok = check_embeddings_ready()
        if not embed_ok:
            log.warning("Embeddings not ready at startup - will work in mock mode only")
    
    log.info(
        "Startup OK | online_search=%s | vector_store=%s", 
        settings.online_search,
        "postgres" if vs.use_pg else "memory"
    )

@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {
        "llm_ready": check_llm_ready(),
        "embeddings_ready": check_embeddings_ready(),
        "vector_store": "postgres" if vs.use_pg else "memory",
        "online_search": settings.online_search,
    }

@app.get("/api/diagnostics")
def diagnostics():
    """Detailed diagnostics for debugging."""
    return {
        "settings": {
            "ollama_base": settings.ollama_base,
            "ollama_model": settings.ollama_model,
            "ollama_embed": settings.ollama_embed,
            "online_search": settings.online_search,
            "require_llm": settings.require_llm,
            "require_embeddings": settings.require_embeddings,
        },
        "vector_store": {
            "type": "postgres" if vs.use_pg else "memory",
            "pg_dsn": bool(settings.pg_dsn),
        },
        "companies_loaded": len(orch.companies()),
    }

def _coerce_to_dict(obj):
    """Robust serializer for dataclasses and objects."""
    # Pydantic v2
    if hasattr(obj, "model_dump") and callable(getattr(obj, "model_dump")):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Pydantic v1
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return obj.dict()
        except Exception:
            pass
    # Dataclass
    try:
        from dataclasses import is_dataclass, asdict
        if is_dataclass(obj):
            return asdict(obj)
    except Exception:
        pass
    # Fallback: instance __dict__
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return obj

@app.get("/api/companies")
def companies():
    """List all available companies."""
    try:
        return [_coerce_to_dict(c) for c in orch.companies()]
    except Exception as e:
        log.exception("companies() failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream/research/{company_id}")
def stream_research(company_id: str, online: bool | None = Query(default=None)):
    """Stream research events for a company."""
    def gen():
        try:
            for ev in orch.research_company_events(company_id, online=online):
                yield {"event": ev["type"], "data": json.dumps(ev)}
        except Exception as e:
            log.error("Research stream error: %s", e)
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
    
    return EventSourceResponse(gen())

@app.get("/api/stream/outreach/{company_id}/preview")
def stream_outreach_preview(
    company_id: str, 
    online: bool | None = Query(default=None), 
    bypass: bool = Query(default=True)
):
    """Stream outreach preview for a company."""
    def gen():
        try:
            for ev in orch.preview_outreach_company_events(
                company_id, online=online, bypass_compliance=bypass
            ):
                yield {"event": ev["type"], "data": json.dumps(ev)}
        except Exception as e:
            log.error("Outreach stream error: %s", e)
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
    
    return EventSourceResponse(gen())

@app.delete("/api/admin/clear-namespace")
def clear_namespace(ns: str = Query(..., description="Namespace to clear, e.g., stc.com.sa#web")):
    """Clear all vectors in a namespace."""
    try:
        deleted = vs.clear_namespace(ns)
        log.info("Cleared namespace %s: deleted %d vectors", ns, deleted)
        return {"ok": True, "namespace": ns, "deleted": deleted}
    except Exception as e:
        log.error("Clear namespace failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream/logs")
def stream_logs():
    """Stream recent log entries (for debugging)."""
    def gen():
        log_file = Path("logs/app.log")
        if log_file.exists():
            with open(log_file, "r") as f:
                # Get last 100 lines
                lines = f.readlines()[-100:]
                for line in lines:
                    yield {"event": "log", "data": json.dumps({"line": line.strip()})}
        yield {"event": "done", "data": json.dumps({"complete": True})}
    
    return EventSourceResponse(gen())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)