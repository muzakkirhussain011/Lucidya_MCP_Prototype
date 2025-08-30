from __future__ import annotations
import os, json, logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.services.vectorstore import VectorStore
from app.services.crm import MiniCRM
from app.services.orchestrator import Orchestrator
from app.tools.llm import check_llm_ready
from app.tools.embeddings import check_embeddings_ready

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("server")

app = FastAPI(title="Lucidya Demo API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

settings = get_settings()
vs = VectorStore()
crm = MiniCRM()
orch = Orchestrator(crm, vs)

@app.get("/api/health")
def health():
    return {
        "llm_ready": check_llm_ready(),
        "embeddings_ready": check_embeddings_ready(),
        "vector_store": "postgres" if vs.use_pg else "memory",
    }

def _coerce_to_dict(obj):
    """
    Robust serializer for Pydantic v1/v2, dataclasses, or plain objects.
    """
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
    # Fallback: instance __dict__ without privates/callables
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    # Last resort
    return obj

@app.get("/api/companies")
def companies():
    try:
        return [_coerce_to_dict(c) for c in orch.companies()]
    except Exception as e:
        log.exception("companies() failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

# --- Streaming (SSE) with online toggle ---
@app.get("/api/stream/research/{company_id}")
def stream_research(company_id: str, online: bool | None = Query(default=None)):
    def gen():
        for ev in orch.research_company_events(company_id, online=online):
            yield {"event": ev["type"], "data": json.dumps(ev)}
    return EventSourceResponse(gen())

@app.get("/api/stream/outreach/{company_id}/preview")
def stream_outreach_preview(company_id: str, online: bool | None = Query(default=None), bypass: bool = True):
    def gen():
        for ev in orch.preview_outreach_company_events(company_id, online=online, bypass_compliance=bypass):
            yield {"event": ev["type"], "data": json.dumps(ev)}
    return EventSourceResponse(gen())

# --- Admin: clear a namespace (domain#web or domain#mock) ---
@app.delete("/api/admin/clear-namespace")
def clear_namespace(ns: str = Query(..., description="Namespace to clear, e.g., stc.com.sa#web or #mock")):
    try:
        deleted = vs.clear_namespace(ns)
        return {"ok": True, "namespace": ns, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
