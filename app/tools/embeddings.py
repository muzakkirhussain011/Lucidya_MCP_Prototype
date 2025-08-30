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
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        raise EmbeddingsNotReady(f"Embeddings timeout after {timeout}s - model may be loading")
    except requests.exceptions.RequestException as e:
        raise EmbeddingsNotReady(f"Embeddings request failed: {e}")

def check_embeddings_ready() -> bool:
    """Check if embeddings model is responsive."""
    s = get_settings()
    try:
        t0 = time.time()
        data = _post("/api/embeddings", {"model": s.ollama_embed, "prompt": "health check"})
        embedding = data.get("embedding")
        ok = bool(embedding and len(embedding) > 0)
        log.info("Embeddings ready=%s latency=%.2fs dims=%d", ok, time.time() - t0, len(embedding) if embedding else 0)
        return ok
    except Exception as e:
        log.warning("Embeddings not ready: %s", e)
        return False

def ollama_embed(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    s = get_settings()
    if not texts:
        return []
    
    try:
        t0 = time.time()
        out = []
        
        for t in texts:
            if not t or not t.strip():
                # Skip empty texts
                continue
                
            data = _post("/api/embeddings", {"model": s.ollama_embed, "prompt": t})
            vec = data.get("embedding")
            
            if not vec:
                log.warning("Empty embedding for text: %s...", t[:50])
                # Use a zero vector as fallback
                vec = [0.0] * 384  # nomic-embed-text default dimension
            
            out.append(vec)
        
        if not out and texts:
            # If all texts were empty or failed, return at least one zero vector
            log.warning("No valid embeddings generated, using zero vectors")
            out = [[0.0] * 384 for _ in texts]
        
        log.info("embed batch=%d latency=%.2fs", len(out), time.time() - t0)
        return out
        
    except Exception as e:
        log.exception("ollama_embed failed: %s", e)
        # Return zero vectors as fallback
        if texts:
            log.warning("Falling back to zero vectors due to embedding failure")
            return [[0.0] * 384 for _ in texts]
        raise EmbeddingsNotReady(str(e))