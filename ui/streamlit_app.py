import os, json, requests, streamlit as st

DEFAULT_API = os.getenv("API_BASE", "http://localhost:8000")
TIMEOUT = 300

st.set_page_config(page_title="Lucidya – Demo UI (Streaming + Logs)", layout="wide")
st.title("Lucidya – Multi-Agent Demo (Streaming + Logs)")

def api_get(api_base: str, path: str):
    r = requests.get(f"{api_base}{path}", timeout=TIMEOUT); r.raise_for_status(); return r.json()

def sse_stream(url: str):
    headers = {"Accept": "text/event-stream"}
    with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        event = "message"; buffer = []
        for raw in r.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            if raw.startswith(":"):
                continue
            if raw.startswith("event:"):
                event = raw.split(":",1)[1].strip()
            elif raw.startswith("data:"):
                data = raw.split(":",1)[1].strip()
                buffer.append(data)
            elif raw == "":
                if buffer:
                    joined = "\n".join(buffer); buffer.clear()
                    try:
                        yield event, json.loads(joined)
                    except Exception:
                        yield event, {"raw": joined}
                event = "message"

# Sidebar
st.sidebar.header("Backend")
api_base = st.sidebar.text_input("API base URL", value=DEFAULT_API)
use_online = st.sidebar.toggle("Use live web search", value=True, help="ON = websearch only (no mock). OFF = mock only (no network).")

ready = False
try:
    h = api_get(api_base, "/api/health")
    ready = bool(h.get("llm_ready") and h.get("embeddings_ready"))
    st.sidebar.success(f"LLM: {h.get('llm_ready')} | Embed: {h.get('embeddings_ready')} | VS: {h.get('vector_store')}")
except Exception as e:
    st.sidebar.error(f"Health failed: {e}")

if "companies" not in st.session_state: st.session_state.companies = []

tabs = st.tabs(["Companies", "Research (Stream)", "Outreach Preview (Stream)"])

# Companies
with tabs[0]:
    st.subheader("Companies")
    if st.button("Load companies"):
        try:
            st.session_state.companies = api_get(api_base, "/api/companies")
            st.success(f"Loaded {len(st.session_state.companies)}.")
        except Exception as e:
            st.error(f"Load failed: {e}")
    if st.session_state.companies:
        st.dataframe(
            [{"id": c["id"], "name": c["name"], "industry": c["industry"], "region": c["region"], "size": c["size"], "domain": c["domain"]} for c in st.session_state.companies],
            use_container_width=True
        )

# Research streaming
with tabs[1]:
    st.subheader("Research with live progress (Markdown streaming)")
    if not st.session_state.companies:
        st.info("Load companies first.")
    else:
        label_map = {f"{c['name']} ({c['id']})": c["id"] for c in st.session_state.companies}
        choice = st.selectbox("Pick a company", list(label_map.keys()))
        cid = label_map[choice]
        company = next(c for c in st.session_state.companies if c["id"] == cid)
        mode = "web" if use_online else "mock"
        ns = f"{company['domain']}#{mode}"

        colA, colB = st.columns([1,1])
        with colA:
            if st.button("Clear cache for this company & mode"):
                try:
                    r = requests.delete(f"{api_base}/api/admin/clear-namespace", params={"ns": ns}, timeout=TIMEOUT)
                    r.raise_for_status()
                    st.success(f"Cleared {ns}: deleted {r.json().get('deleted', 0)} rows")
                except Exception as e:
                    st.error(f"Clear failed: {e}")
        with colB:
            st.info(f"Streaming namespace will be **{ns}**")

        log_box = st.empty()
        llm_box = st.empty()
        final_box = st.empty()

        if st.button("Start streaming research", disabled=not ready):
            try:
                llm_md = ""
                rows = []
                stream_url = f"{api_base}/api/stream/research/{cid}?online={'true' if use_online else 'false'}"
                for ev, payload in sse_stream(stream_url):
                    if ev in ("start","search","search_results","search_error","fetch_start","fetch_done","mock_seed","embedded","retrieve","no_content"):
                        rows.append(f"[{ev}] {payload}")
                        log_box.markdown("```\n" + "\n".join(rows[-40:]) + "\n```")
                        if payload.get("namespace"):
                            st.caption(f"Namespace: `{payload['namespace']}`")
                    elif ev == "llm_delta":
                        llm_md += payload.get("delta","")
                        llm_box.markdown(llm_md)  # render as Markdown
                    elif ev == "llm_complete":
                        rows.append(f"[llm_complete] {payload}")
                        log_box.markdown("```\n" + "\n".join(rows[-40:]) + "\n```")
                    elif ev == "done":
                        final_box.markdown("### Final summary\n\n" + payload.get("internal_summary",""))
                        st.success("Research complete.")
            except Exception as e:
                st.error(f"Streaming failed: {e}")

# Outreach preview streaming
with tabs[2]:
    st.subheader("Outreach writing (preview, Markdown streaming)")
    if not st.session_state.companies:
        st.info("Load companies first.")
    else:
        label_map = {f"{c['name']} ({c['id']})": c["id"] for c in st.session_state.companies}
        cid = label_map[st.selectbox("Pick a company", list(label_map.keys()), key="outreachpick")]
        log_box = st.empty(); live_body = st.empty(); final_box = st.empty()
        bypass = st.checkbox("Bypass compliance (preview)", value=True)

        if st.button("Start streaming outreach", disabled=not ready):
            try:
                body_md = ""; rows = []
                stream_url = f"{api_base}/api/stream/outreach/{cid}/preview?online={'true' if use_online else 'false'}&bypass={'true' if bypass else 'false'}"
                for ev, payload in sse_stream(stream_url):
                    if ev in ("start","contacts","compose_begin","context_hits"):
                        rows.append(f"[{ev}] {payload}"); log_box.markdown("```\n" + "\n".join(rows[-40:]) + "\n```")
                    elif ev == "llm_delta":
                        body_md += payload.get("delta",""); live_body.markdown(body_md)
                    elif ev == "final_email":
                        final_box.markdown(f"**Subject:** {payload['subject']}\n\n{payload['body']}")
                    elif ev == "done":
                        st.success("Outreach preview finished.")
            except Exception as e:
                st.error(f"Streaming failed: {e}")
