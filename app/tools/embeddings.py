# app/tools/embeddings.py
from __future__ import annotations
import logging, time, requests
from app.config import get_settings

log = logging.getLogger("llm")
EMB_TIMEOUT = 600

class EmbeddingsNotReady(RuntimeError): ...

def _post(path: str, payload: dict, timeout: int = EMB_TIMEOUT):
    s = get_settings()
    url = f"{s.ollama_base}{path}"
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

def check_embeddings_ready() -> bool:
    s = get_settings()
    try:
        t0 = time.time()
        data = _post("/api/embeddings", {"model": s.ollama_embed, "prompt": "health"})
        ok = bool(data and data.get("embedding"))
        log.info("Embeddings ready=%s latency=%.2fs", ok, time.time() - t0)
        return ok
    except Exception as e:
        log.warning("Embeddings not ready: %s", e)
        return False

def ollama_embed(texts: list[str]) -> list[list[float]]:
    s = get_settings()
    try:
        t0 = time.time()
        out = []
        for t in texts:
            data = _post("/api/embeddings", {"model": s.ollama_embed, "prompt": t})
            vec = data.get("embedding")
            if not vec:
                raise EmbeddingsNotReady("empty embedding")
            out.append(vec)
        log.info("embed batch=%d latency=%.2fs", len(out), time.time() - t0)
        return out
    except Exception as e:
        log.exception("ollama_embed failed: %s", e)
        raise EmbeddingsNotReady(str(e))
