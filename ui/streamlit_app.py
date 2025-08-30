import os, json, requests, streamlit as st

DEFAULT_API = os.getenv("API_BASE", "http://localhost:8000")
TIMEOUT = 300

st.set_page_config(page_title="Lucidya – AI CX Research & Outreach", layout="wide", page_icon="🔍")
st.title("🔍 Lucidya – Multi-Agent CX Research & Outreach")
st.caption("Real-time web research → Evidence-based insights → Compliant outreach")

def api_get(api_base: str, path: str):
    r = requests.get(f"{api_base}{path}", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()

def sse_stream(url: str):
    headers = {"Accept": "text/event-stream"}
    with requests.get(url, headers=headers, stream=True, timeout=TIMEOUT) as r:
        r.raise_for_status()
        event = "message"
        buffer = []
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
                    joined = "\n".join(buffer)
                    buffer.clear()
                    try:
                        yield event, json.loads(joined)
                    except Exception:
                        yield event, {"raw": joined}
                event = "message"

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    api_base = st.text_input("API base URL", value=DEFAULT_API)
    use_online = st.toggle(
        "🌐 Live Web Search", 
        value=True, 
        help="ON = Real web search & fetch\nOFF = Mock data only (no network)"
    )
    
    # System Health Check
    st.divider()
    st.subheader("🏥 System Status")
    ready = False
    try:
        h = api_get(api_base, "/api/health")
        llm_ready = h.get("llm_ready", False)
        embed_ready = h.get("embeddings_ready", False)
        vs_type = h.get("vector_store", "unknown")
        ready = llm_ready and embed_ready
        
        if ready:
            st.success("✅ All systems operational")
        else:
            st.error("⚠️ Some systems not ready")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("LLM", "Ready" if llm_ready else "Not Ready", 
                     delta=None, delta_color="normal" if llm_ready else "inverse")
        with col2:
            st.metric("Embeddings", "Ready" if embed_ready else "Not Ready",
                     delta=None, delta_color="normal" if embed_ready else "inverse")
        st.info(f"Vector Store: **{vs_type}**")
    except Exception as e:
        st.error(f"❌ Health check failed: {e}")

if "companies" not in st.session_state:
    st.session_state.companies = []

# Main tabs
tab1, tab2, tab3 = st.tabs(["🏢 Companies", "🔬 Research (Live Stream)", "✉️ Outreach Preview (Live Stream)"])

# Companies Tab
with tab1:
    st.subheader("Available Companies")
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔄 Load Companies", type="primary", use_container_width=True):
            try:
                st.session_state.companies = api_get(api_base, "/api/companies")
                st.success(f"✅ Loaded {len(st.session_state.companies)} companies")
            except Exception as e:
                st.error(f"Failed to load: {e}")
    
    if st.session_state.companies:
        # Display companies as cards
        for c in st.session_state.companies:
            with st.expander(f"**{c['name']}** - {c['industry']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Region:** {c['region']}")
                    st.write(f"**Size:** {c['size']:,} employees")
                with col2:
                    st.write(f"**Domain:** {c['domain']}")
                    st.write(f"**Website:** {c['website']}")
                with col3:
                    st.write(f"**ID:** `{c['id']}`")
                
                if c.get('challenges'):
                    st.write("**Key Challenges:**")
                    for ch in c['challenges']:
                        st.write(f"• {ch}")
    else:
        st.info("👆 Click 'Load Companies' to start")

# Research Tab
with tab2:
    st.subheader("🔬 Live Research with Evidence Tracking")
    
    if not st.session_state.companies:
        st.warning("⚠️ Please load companies first in the Companies tab")
    else:
        # Company selector
        label_map = {f"{c['name']} ({c['id']})": c["id"] for c in st.session_state.companies}
        choice = st.selectbox("Select a company to research:", list(label_map.keys()))
        cid = label_map[choice]
        company = next(c for c in st.session_state.companies if c["id"] == cid)
        
        # Mode indicator
        mode = "🌐 Web Search" if use_online else "💾 Mock Data"
        ns = f"{company['domain']}#{'web' if use_online else 'mock'}"
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            st.info(f"**Mode:** {mode}")
        with col2:
            st.info(f"**Namespace:** `{ns}`")
        with col3:
            if st.button("🗑️ Clear Cache", help="Clear vector store for this company/mode"):
                try:
                    r = requests.delete(f"{api_base}/api/admin/clear-namespace", 
                                      params={"ns": ns}, timeout=TIMEOUT)
                    r.raise_for_status()
                    st.success(f"Cleared {r.json().get('deleted', 0)} vectors")
                except Exception as e:
                    st.error(f"Clear failed: {e}")
        
        # Research sections
        progress_placeholder = st.empty()
        log_container = st.container()
        summary_container = st.container()
        evidence_container = st.container()
        
        if st.button("🚀 Start Research", type="primary", disabled=not ready):
            # Clear previous results
            progress_placeholder.empty()
            
            with st.spinner("Researching..."):
                try:
                    llm_md = ""
                    log_entries = []
                    evidence_sources = []
                    final_summary = ""
                    
                    stream_url = f"{api_base}/api/stream/research/{cid}?online={'true' if use_online else 'false'}"
                    
                    # Progress bar
                    progress_bar = progress_placeholder.progress(0, text="Starting research...")
                    
                    for ev, payload in sse_stream(stream_url):
                        # Update progress based on event type
                        if ev == "start":
                            progress_bar.progress(5, text="🔍 Initializing research...")
                            log_entries.append(f"✅ Started research for {payload.get('company')}")
                            
                        elif ev == "search":
                            progress_bar.progress(20, text=f"🔎 Searching: {payload.get('query', '')[:50]}...")
                            log_entries.append(f"🔍 Search: {payload.get('query', '')}")
                            
                        elif ev == "search_results":
                            count = payload.get('count', 0)
                            log_entries.append(f"📊 Found {count} results")
                            
                        elif ev == "fetch_start":
                            progress_bar.progress(40, text=f"📥 Fetching: {payload.get('host', 'content')}...")
                            
                        elif ev == "fetch_done":
                            if payload.get('ok'):
                                log_entries.append(f"✅ Fetched {payload.get('chars', 0):,} chars from {payload.get('host', 'unknown')}")
                            else:
                                log_entries.append(f"❌ Failed to fetch from {payload.get('host', 'unknown')}")
                                
                        elif ev == "embedding_start":
                            progress_bar.progress(60, text="🧮 Creating embeddings...")
                            
                        elif ev == "embedded":
                            progress_bar.progress(70, text=f"💾 Stored {payload.get('chunks', 0)} chunks")
                            log_entries.append(f"💾 Embedded {payload.get('chunks', 0)} chunks")
                            
                        elif ev == "retrieve":
                            progress_bar.progress(80, text="🎯 Finding relevant context...")
                            log_entries.append(f"🎯 Retrieved {payload.get('hits', 0)} relevant chunks")
                            
                        elif ev == "llm_begin":
                            progress_bar.progress(90, text="✍️ Generating insights...")
                            
                        elif ev == "llm_delta":
                            llm_md += payload.get("delta", "")
                            # Update summary in real-time
                            with summary_container:
                                st.markdown("### 📝 AI Summary (Live)")
                                st.markdown(llm_md)
                                
                        elif ev == "evidence":
                            evidence_sources = payload.get("sources", [])
                            log_entries.append(f"📚 Collected {payload.get('count', 0)} evidence sources")
                            
                        elif ev == "done":
                            progress_bar.progress(100, text="✅ Research complete!")
                            final_summary = payload.get("internal_summary", "")
                        
                        # Update log display
                        with log_container:
                            with st.expander("📋 Research Log", expanded=False):
                                for entry in log_entries[-20:]:  # Show last 20 entries
                                    st.caption(entry)
                    
                    # Display final results
                    with summary_container:
                        st.markdown("### 📝 Final Summary")
                        st.markdown(final_summary or llm_md)
                    
                    # Display evidence sources
                    if evidence_sources:
                        with evidence_container:
                            st.markdown("### 📚 Evidence Sources")
                            st.caption(f"Research based on {len(evidence_sources)} sources:")
                            for i, src in enumerate(evidence_sources, 1):
                                with st.expander(f"{i}. {src.get('title', 'Untitled')[:80]}"):
                                    st.write(f"**URL:** {src.get('url', '')}")
                                    if src.get('snippet'):
                                        st.write(f"**Preview:** {src.get('snippet', '')}")
                    
                    st.success("✅ Research completed successfully!")
                    
                except Exception as e:
                    st.error(f"❌ Research failed: {e}")

# Outreach Tab
with tab3:
    st.subheader("✉️ Outreach Email Preview")
    
    if not st.session_state.companies:
        st.warning("⚠️ Please load companies first in the Companies tab")
    else:
        # Company selector
        label_map = {f"{c['name']} ({c['id']})": c["id"] for c in st.session_state.companies}
        cid = label_map[st.selectbox("Select a company for outreach:", 
                                     list(label_map.keys()), key="outreach_company")]
        
        # Options
        col1, col2 = st.columns(2)
        with col1:
            bypass = st.checkbox("🔓 Bypass compliance checks", value=True, 
                               help="For preview/testing only")
        with col2:
            mode = "🌐 Web Search" if use_online else "💾 Mock Data"
            st.info(f"**Mode:** {mode}")
        
        # Outreach sections
        contacts_container = st.container()
        email_container = st.container()
        log_container = st.container()
        
        if st.button("📤 Generate Outreach", type="primary", disabled=not ready):
            with st.spinner("Generating outreach emails..."):
                try:
                    contacts = []
                    emails = []
                    log_entries = []
                    current_email = {"subject": "", "body": ""}
                    
                    stream_url = (f"{api_base}/api/stream/outreach/{cid}/preview"
                                f"?online={'true' if use_online else 'false'}"
                                f"&bypass={'true' if bypass else 'false'}")
                    
                    for ev, payload in sse_stream(stream_url):
                        if ev == "finding_contacts":
                            log_entries.append(f"🔍 Finding contacts via {payload.get('method', 'unknown')}")
                            
                        elif ev == "contacts":
                            contacts = payload.get("contacts", [])
                            log_entries.append(f"👥 Found {payload.get('count', 0)} contacts")
                            with contacts_container:
                                st.markdown("### 👥 Contacts Found")
                                for c in contacts:
                                    st.write(f"• **{c['name']}** - {c['role']} ({c['email']})")
                                    
                        elif ev == "compose_begin":
                            current_email = {
                                "person": payload.get("person"),
                                "email": payload.get("email"),
                                "subject": "",
                                "body": "",
                                "compliance": payload.get("compliance"),
                                "reason": payload.get("reason")
                            }
                            if payload.get("compliance"):
                                log_entries.append(f"✅ Composing for {payload.get('person')}")
                            else:
                                log_entries.append(f"⚠️ Skipping {payload.get('person')}: {payload.get('reason')}")
                                
                        elif ev == "subject":
                            current_email["subject"] = payload.get("subject", "")
                            
                        elif ev == "llm_delta":
                            current_email["body"] += payload.get("delta", "")
                            # Live update of email being composed
                            with email_container:
                                st.markdown(f"### ✍️ Composing: {current_email.get('person', 'Unknown')}")
                                if current_email.get("subject"):
                                    st.write(f"**Subject:** {current_email['subject']}")
                                st.markdown(current_email["body"])
                                
                        elif ev == "final_email":
                            email = {
                                "person": payload.get("person"),
                                "email": payload.get("email"),
                                "subject": payload.get("subject"),
                                "body": payload.get("body")
                            }
                            emails.append(email)
                            log_entries.append(f"✅ Email ready for {payload.get('person')}")
                        
                        # Update log
                        with log_container:
                            with st.expander("📋 Generation Log", expanded=False):
                                for entry in log_entries[-10:]:
                                    st.caption(entry)
                    
                    # Display final emails
                    if emails:
                        st.markdown("### 📧 Generated Emails")
                        for email in emails:
                            with st.expander(f"Email to: {email['person']} ({email['email']})"):
                                st.write(f"**To:** {email['email']}")
                                st.write(f"**Subject:** {email['subject']}")
                                st.divider()
                                st.markdown(email['body'])
                        
                        st.success(f"✅ Generated {len(emails)} outreach emails!")
                    else:
                        st.warning("No emails were generated")
                        
                except Exception as e:
                    st.error(f"❌ Outreach generation failed: {e}")