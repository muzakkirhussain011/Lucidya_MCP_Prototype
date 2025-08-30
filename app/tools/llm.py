# app/tools/llm.py
from __future__ import annotations
import re, json, time, logging, requests
from typing import List, Tuple
from app.config import get_settings

log = logging.getLogger("llm")
OLLAMA_TIMEOUT_SECONDS = 600

# Strip Ollama <think> blocks just in case
_THINK_BLOCK = re.compile(r"<\s*think\s*>.*?<\s*/\s*think\s*>", re.I | re.S)

# --- space repair helpers ---

_CAMEL          = re.compile(r"([a-z])([A-Z])")                 # fooBar -> foo Bar
_UC_CLUSTER     = re.compile(r"([A-Z]{2,})([A-Z][a-z])")        # STCGroup -> STC Group
_LONG_LOWER     = re.compile(r"\b[a-z]{12,}\b")                 # aggressive split
_NUM_LET        = re.compile(r"(\d)([A-Za-z])")                 # 20,000employees -> 20,000 employees
_LET_NUM        = re.compile(r"([A-Za-z])(\d)")                 # v2 -> v 2
_PAREN_OPEN     = re.compile(r"([A-Za-z0-9])\(")
_PAREN_CLOSE    = re.compile(r"\)([A-Za-z0-9])")
_BOLD_GLUE      = re.compile(r"\*\*(\S)")                       # **Word -> ** Word
_PUNCT_SPACE    = re.compile(r"(\S)([,:;])(?!\s)")              # foo,bar -> foo, bar
# FIX: use fixed-width lookbehind to avoid breaking http:// https:// file:// etc.
_SLASH_SPACE    = re.compile(r"(?<!://)(\S)/(?!/)(\S)")         # a/b -> a / b (but don't break URLs)
_LINE_BULLET    = re.compile(r"(^|\n)-(?=\S)")
_MULTI_BLANKS   = re.compile(r"\n{2,}")

def _split_concatenated_word(token: str) -> str:
    try:
        import wordninja
        parts = wordninja.split(token)
        return " ".join(parts) if parts else token
    except Exception:
        return token

def _deglue_text(s: str) -> str:
    if not s: return s
    s = _PAREN_OPEN.sub(r"\1 (", s); s = _PAREN_CLOSE.sub(r") \1", s)
    s = _PUNCT_SPACE.sub(r"\1\2 ", s)
    s = _SLASH_SPACE.sub(r"\1 / \2", s)
    s = _CAMEL.sub(r"\1 \2", s)
    s = _UC_CLUSTER.sub(r"\1 \2", s)
    s = _NUM_LET.sub(r"\1 \2", s)
    s = _LET_NUM.sub(r"\1 \2", s)
    s = _BOLD_GLUE.sub(r"** \1", s)
    s = _LINE_BULLET.sub(r"\1- ", s)
    s = _LONG_LOWER.sub(lambda m: _split_concatenated_word(m.group(0)), s)
    s = _MULTI_BLANKS.sub("\n", s)
    return s

# --- core helpers ---

class LLMNotReady(RuntimeError): ...

def _clean(t: str) -> str:
    return _THINK_BLOCK.sub("", t or "").strip()

def _post(path: str, payload: dict, timeout: int = OLLAMA_TIMEOUT_SECONDS):
    s = get_settings()
    payload = dict(payload or {})
    payload.setdefault("think", s.ollama_think)  # default False (no <think> in response)
    url = f"{s.ollama_base}{path}"
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()

def check_llm_ready() -> bool:
    s = get_settings()
    try:
        t0 = time.time()
        data = _post("/api/generate", {
            "model": s.ollama_model, "prompt": "ping",
            "options": {"temperature": 0.0}, "stream": False
        })
        resp = (data.get("response") or "").strip()
        ok = bool(resp)
        log.info("LLM ready=%s latency=%.2fs", ok, time.time() - t0)
        return ok
    except Exception as e:
        log.warning("LLM not ready: %s", e)
        return False

def ollama_generate(prompt: str, system: str = "", temperature: float = 0.3) -> str:
    s = get_settings()
    try:
        t0 = time.time()
        data = _post("/api/generate", {
            "model": s.ollama_model,
            "prompt": prompt,
            "options": {"temperature": temperature},
            "system": system,
            "stream": False
        })
        resp = _clean(data.get("response") or "")
        resp = _deglue_text(resp)
        if not resp:
            raise LLMNotReady("Empty response from LLM.")
        log.info("LLM generate chars=%d latency=%.2fs", len(resp), time.time() - t0)
        return resp
    except Exception as e:
        log.exception("ollama_generate failed: %s", e)
        raise LLMNotReady(f"Ollama text model not ready: {e}")

# ---------- Markdown Streaming ----------

def _chunk_markdown(buffer: str) -> tuple[list[str], str]:
    """
    Split buffer into clean Markdown chunks:
      • flush at newline boundaries
      • flush at sentence ends ([.!?] + space/newline)
      • flush before a new '- ' bullet
    """
    chunks: list[str] = []
    last = 0
    i = 0
    while i < len(buffer):
        flush = False
        c = buffer[i]
        if c == "\n":
            flush = True
        elif c in ".!?" and i + 1 < len(buffer) and buffer[i + 1] in " \n":
            flush = True
        elif buffer[i:i+2] == "- " and i > last:
            chunks.append(buffer[last:i]); last = i
        if flush:
            chunks.append(buffer[last:i+1]); last = i + 1
        i += 1
    remainder = buffer[last:]
    chunks = [c for c in chunks if c]
    return chunks, remainder

def ollama_generate_markdown_stream(prompt: str, system: str = "", temperature: float = 0.3):
    """
    Streams **markdown-friendly chunks** (lines/paragraphs/bullets) from Ollama,
    and repairs glued text on the fly so the UI renders readable Markdown.
    """
    s = get_settings()
    url = f"{s.ollama_base}/api/generate"
    payload = {
        "model": s.ollama_model,
        "prompt": prompt,
        "options": {"temperature": temperature},
        "system": system,
        "stream": True,
        "think": s.ollama_think,
    }

    buf = ""
    total = 0
    t0 = time.time()
    with requests.post(url, json=payload, stream=True, timeout=OLLAMA_TIMEOUT_SECONDS) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            raw = _clean(data.get("response", ""))
            if not raw:
                continue
            buf += raw
            chunks, buf = _chunk_markdown(buf)
            for ch in chunks:
                clean = _deglue_text(ch)
                total += len(clean)
                yield clean
        if buf.strip():
            yield _deglue_text(buf)

    log.info("LLM md_stream total_chars=%d latency=%.2fs", total, time.time() - t0)
