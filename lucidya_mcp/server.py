# mcp/server.py
# Compatible with FastMCP 2.x or the official MCP Python SDK fallback.

from __future__ import annotations

# 1) Import FastMCP from fastmcp if available; otherwise from the official SDK.
try:
    from fastmcp import FastMCP  # FastMCP 2.x preferred
    USING_FASTMCP = True
except ImportError:  # fallback to official SDK's fastmcp shim
    from mcp.server.fastmcp import FastMCP  # official MCP SDK
    USING_FASTMCP = False

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]  # project root: D:\Lucidiya
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 2) Bring in your app tools
from app.tools.search import ddg_search
from app.tools.fetch import http_get_text
from app.tools.embeddings import ollama_embed
from app.tools.llm import ollama_generate
from app.services.vectorstore import VectorStore
from app.config import get_settings

# One in-process vector store instance for MCP tools
_vs = VectorStore()

# Create the MCP server
mcp = FastMCP(name="lucidya-tools")

# --- Tools ---

@mcp.tool()
def web_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Search the web (DuckDuckGo via `ddgs`) and return a list of hits with title, href, body.
    """
    return ddg_search(query, max_results=max_results)

@mcp.tool()
def web_fetch(url: str) -> str:
    """
    Fetch a URL and return a clean, text-only body (HTML stripped).
    """
    return http_get_text(url)

@mcp.tool()
def embed(texts: list[str]) -> list[list[float]]:
    """
    Create embeddings for a list of strings using your Ollama embeddings model.
    """
    return ollama_embed(texts)

@mcp.tool()
def llm(prompt: str, system: str = "", temperature: float = 0.3, max_tokens: int = 512) -> str:
    """
    Generate text from your Ollama LLM (thinking disabled by default in app config).
    """
    return ollama_generate(prompt, system=system, temperature=temperature, max_tokens=max_tokens)

@mcp.tool()
def vs_upsert(domain: str, url: str, content: str, embedding: list[float]) -> str:
    """
    Upsert a (domain, url, content, embedding) record into the vector store.
    """
    _vs.upsert(domain, url, content, embedding)
    return "ok"

@mcp.tool()
def vs_search(domain: str, query: str, top_k: int = 5) -> list[dict]:
    """
    Semantic search over the vector store for a given domain using an on-the-fly embedded query.
    """
    qv = ollama_embed([query])[0]
    return _vs.search(domain, qv, top_k=top_k)

@mcp.tool()
def diagnostics() -> dict:
    """
    Return current model selections and modes for quick verification from the Inspector.
    """
    s = get_settings()
    return {
        "models": {"text": s.ollama_model, "embed": s.ollama_embed, "think": s.ollama_think},
        "modes": {"online_search": s.online_search, "vector_store": "pgvector" if _vs.use_pg else "memory"},
        "using_fastmcp": USING_FASTMCP,
    }

# 3) Run the server over stdio
if __name__ == "__main__":
    mcp.run()
