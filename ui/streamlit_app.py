# file: ui/streamlit_app.py
import streamlit as st
import requests
import json
from datetime import datetime
import pandas as pd
import time
from collections import defaultdict
import os

st.set_page_config(
    page_title="Lucidya MCP Prototype",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Lucidya Multi-Agent CX Platform")
st.caption("Real-time agent orchestration with Ollama streaming and MCP integration")

# Configure API base via environment; default to loopback
API_BASE = os.environ.get("API_BASE", "http://127.0.0.1:8000")

# Initialize session state
if "pipeline_logs" not in st.session_state:
    st.session_state.pipeline_logs = []
if "current_prospect" not in st.session_state:
    st.session_state.current_prospect = None
if "company_outputs" not in st.session_state:
    st.session_state.company_outputs = {}
if "handoff_packets" not in st.session_state:
    st.session_state.handoff_packets = {}

# Sidebar
with st.sidebar:
    st.header("System Status")
    
    # Health check
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=8)
        health = resp.json()

        if health.get("status") == "healthy":
            st.success("✅ System Healthy")
            
            with st.expander("System Components"):
                # Ollama status
                ollama_status = health.get("ollama", {})
                if ollama_status.get("connected"):
                    st.success(f"✅ Ollama: {ollama_status.get('model', 'Unknown')}")
                else:
                    st.error("❌ Ollama: Disconnected")
                
                # MCP servers status
                mcp_status = health.get("mcp", {})
                for server, status in mcp_status.items():
                    if status == "healthy":
                        st.success(f"✅ MCP {server.title()}: Running")
                    else:
                        st.error(f"❌ MCP {server.title()}: {status}")
                
                # Vector store status
                if health.get("vector_store"):
                    st.success("✅ Vector Store: Initialized")
                else:
                    st.warning("⚠️ Vector Store: Not initialized")
        else:
            st.error("❌ System Unhealthy")
    except Exception as e:
        st.error(f"❌ API Offline at {API_BASE}: {e}")
    
    st.divider()
    
    # System controls
    st.header("System Controls")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Reset", help="Clear all data and reload"):
            with st.spinner("Resetting..."):
                try:
                    result = requests.post(f"{API_BASE}/reset").json()
                    st.success(f"✅ Reset: {result['companies_loaded']} companies")
                    st.session_state.company_outputs = {}
                    st.rerun()
                except Exception as e:
                    st.error(f"Reset failed: {e}")
    
    with col2:
        if st.button("🔍 Check", help="Verify system health"):
            st.rerun()

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Pipeline", "📊 Prospects", "🔍 Details", "🧪 Dev Tools"])

# Pipeline Tab
with tab1:
    st.header("Pipeline Execution")
    st.markdown("Watch the complete agent orchestration workflow with MCP interactions in real-time")
    
    # Pipeline controls
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        company_ids = st.text_input(
            "Company IDs",
            placeholder="acme,techcorp,retailplus (or leave empty for all)",
            help="Comma-separated list of company IDs to process"
        )
    
    with col2:
        display_mode = st.selectbox(
            "Display Mode",
            ["Complete Workflow", "Summary Only", "Content Only"],
            help="Choose what information to display"
        )
    
    with col3:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button("▶️ Run Pipeline", type="primary", use_container_width=True):
            st.session_state.running = True
            st.session_state.pipeline_logs = []
            st.session_state.company_outputs = {}
    
    # Pipeline execution display
    if st.session_state.get("running"):
        
        # Create display containers
        progress_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0, text="Initializing pipeline...")
            status_text = st.empty()
        
        # Main display area
        if display_mode == "Complete Workflow":
            # Create columns for workflow and content
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.subheader("🔄 Agent Workflow & MCP Interactions")
                workflow_container = st.container()
                workflow_display = workflow_container.empty()
            
            with col2:
                st.subheader("📝 Generated Content by Company")
                # Single placeholder updated on each token
                content_area = st.empty()
        
        elif display_mode == "Content Only":
            st.subheader("📝 Generated Content by Company")
            content_area = st.empty()
        
        else:  # Summary Only
            st.subheader("📋 Execution Summary")
            summary_container = st.empty()
        
        # Process the pipeline stream
        try:
            # Parse company IDs
            ids = None
            if company_ids:
                ids = [id.strip() for id in company_ids.split(",") if id.strip()]
            
            # Start streaming
            response = requests.post(
                f"{API_BASE}/run",
                json={"company_ids": ids},
                stream=True,
                timeout=60
            )
            
            # Initialize tracking variables
            workflow_logs = []
            current_agent = None
            current_company = None
            agents_completed = set()
            total_agents = 8
            company_outputs = defaultdict(lambda: {"summary": "", "email": "", "status": "processing"})
            mcp_interactions = []
            
            # Helper to render the accumulated content once per update
            def render_content():
                if display_mode == "Summary Only":
                    return
                lines = []
                for company in sorted(company_outputs.keys()):
                    outputs = company_outputs[company]
                    lines.append(f"### 🏢 {company}\n")
                    # Summary
                    lines.append("**📝 Summary**")
                    summary_text = outputs.get("final_summary") or outputs.get("summary") or ""
                    lines.append(summary_text if summary_text else "_No summary yet_\n")
                    # Email
                    lines.append("**✉️ Email Draft**")
                    email_val = outputs.get("final_email") or outputs.get("email") or ""
                    if isinstance(email_val, dict):
                        subj = email_val.get("subject", "")
                        body = email_val.get("body", "")
                        lines.append(f"Subject: {subj}\n\n{body}\n")
                    elif email_val:
                        lines.append(f"{email_val}\n")
                    else:
                        lines.append("_No email yet_\n")
                    lines.append("\n---\n")
                # Overwrite the single placeholder with the assembled markdown
                content_area.markdown("\n".join(lines))
            
            # Process stream
            for line in response.iter_lines():
                if line:
                    try:
                        event = json.loads(line)
                        
                        # Track current company
                        payload = event.get("payload", {})
                        if payload.get("company_name"):
                            current_company = payload["company_name"]
                        elif payload.get("company"):
                            current_company = payload["company"]
                        elif payload.get("prospect", {}).get("company", {}).get("name"):
                            current_company = payload["prospect"]["company"]["name"]
                        
                        # Update progress
                        if event.get("agent"):
                            current_agent = event["agent"]
                            if event["type"] == "agent_end":
                                agents_completed.add(current_agent)
                                progress = len(agents_completed) / total_agents
                                progress_bar.progress(progress, 
                                    text=f"Processing: {current_agent.title()} ({len(agents_completed)}/{total_agents})")
                        
                        # Handle different event types
                        if event["type"] == "agent_start":
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": event["agent"].title(),
                                "📌 Action": "▶️ Started",
                                "🏢 Company": current_company or "All",
                                "💬 Details": event["message"]
                            })
                            status_text.info(f"🔄 {event['agent'].title()}: {event['message']}")
                        
                        elif event["type"] == "mcp_call":
                            mcp_server = event["payload"].get("mcp_server", "unknown")
                            method = event["payload"].get("method", "unknown")
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": current_agent.title() if current_agent else "System",
                                "📌 Action": f"🔌 MCP Call",
                                "🏢 Company": current_company or "All",
                                "💬 Details": f"→ {mcp_server.upper()}: {method}"
                            })
                        
                        elif event["type"] == "mcp_response":
                            mcp_server = event["payload"].get("mcp_server", "unknown")
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": current_agent.title() if current_agent else "System",
                                "📌 Action": f"📥 MCP Response",
                                "🏢 Company": current_company or "All",
                                "💬 Details": f"← {mcp_server.upper()}: {event['message']}"
                            })
                        
                        elif event["type"] == "agent_end":
                            details = event["message"]
                            if event.get("payload"):
                                payload = event["payload"]
                                extra = []
                                if "facts_count" in payload:
                                    extra.append(f"Facts: {payload['facts_count']}")
                                if "contacts_count" in payload:
                                    extra.append(f"Contacts: {payload['contacts_count']}")
                                if "fit_score" in payload:
                                    extra.append(f"Score: {payload['fit_score']:.2f}")
                                if "thread_id" in payload:
                                    extra.append(f"Thread: {payload['thread_id'][:8]}...")
                                if extra:
                                    details += f" ({', '.join(extra)})"
                            
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": event["agent"].title(),
                                "📌 Action": "✅ Completed",
                                "🏢 Company": current_company or "All",
                                "💬 Details": details
                            })
                        
                        elif event["type"] == "company_start":
                            company = event["payload"]["company"]
                            industry = event["payload"].get("industry", "Unknown")
                            size = event["payload"].get("size", 0)
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": "Writer",
                                "📌 Action": "🏢 Company",
                                "🏢 Company": company,
                                "💬 Details": f"Starting: {company} ({industry}, {size} employees)"
                            })
                        
                        elif event["type"] == "llm_token":
                            payload = event.get("payload", {})
                            token = payload.get("token", "")
                            token_type = payload.get("type", "")
                            company = payload.get("company_name") or payload.get("company") or current_company

                            if company and display_mode != "Summary Only":
                                if token_type == "summary":
                                    company_outputs[company]["summary"] += token
                                elif token_type == "email":
                                    company_outputs[company]["email"] += token
                                # Update the single content area
                                render_content()
                        
                        elif event["type"] == "llm_done":
                            payload = event.get("payload", {})
                            company = payload.get("company_name") or payload.get("company") or current_company
                            if company:
                                company_outputs[company]["status"] = "completed"
                                if "summary" in payload:
                                    company_outputs[company]["final_summary"] = payload["summary"]
                                if "email" in payload:
                                    company_outputs[company]["final_email"] = payload["email"]
                                render_content()
                            
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": "Writer",
                                "📌 Action": "✅ Generated",
                                "🏢 Company": company or "Unknown",
                                "💬 Details": "Content generation complete"
                            })
                        
                        elif event["type"] == "policy_block":
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": "Compliance",
                                "📌 Action": "❌ Blocked",
                                "🏢 Company": current_company or "Unknown",
                                "💬 Details": event["payload"].get("reason", "Policy violation")
                            })
                        
                        elif event["type"] == "policy_pass":
                            workflow_logs.append({
                                "⏰ Time": datetime.now().strftime("%H:%M:%S"),
                                "🤖 Agent": "Compliance",
                                "📌 Action": "✅ Passed",
                                "🏢 Company": current_company or "Unknown",
                                "💬 Details": "All compliance checks passed"
                            })
                        
                        # Update displays based on mode
                        if display_mode == "Complete Workflow":
                            # Update workflow display
                            if workflow_logs:
                                df = pd.DataFrame(workflow_logs[-50:])  # Show last 50 entries
                                workflow_display.dataframe(
                                    df,
                                    use_container_width=True,
                                    hide_index=True,
                                    height=400
                                )
                            # Content display handled by render_content()
                        
                        elif display_mode == "Content Only":
                            # Content display handled by render_content()
                            pass
                        
                        else:  # Summary Only
                            # Show high-level statistics
                            summary_stats = {
                                "Total Events": len(workflow_logs),
                                "Agents Run": len(agents_completed),
                                "Companies Processed": len(set(log.get("🏢 Company", "Unknown") for log in workflow_logs if log.get("🏢 Company") != "All")),
                                "MCP Calls": len([log for log in workflow_logs if "MCP Call" in log.get("📌 Action", "")]),
                                "MCP Responses": len([log for log in workflow_logs if "MCP Response" in log.get("📌 Action", "")]),
                                "Current Agent": current_agent.title() if current_agent else "None",
                                "Current Company": current_company or "None"
                            }
                            summary_container.json(summary_stats)
                    
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        st.error(f"Error processing event: {e}")
            
            # Pipeline complete
            progress_bar.progress(1.0, text="✅ Pipeline Complete!")
            status_text.success("✅ Pipeline execution completed successfully!")
            
            # Store outputs in session state
            st.session_state.pipeline_logs = workflow_logs
            st.session_state.company_outputs = dict(company_outputs)
            
            # Show final summary
            st.divider()
            st.subheader("📊 Execution Summary")
            
            # Calculate statistics
            companies_processed = set(log.get("🏢 Company", "Unknown") for log in workflow_logs if log.get("🏢 Company") not in ["All", None])
            mcp_calls = [log for log in workflow_logs if "MCP Call" in log.get("📌 Action", "")]
            mcp_responses = [log for log in workflow_logs if "MCP Response" in log.get("📌 Action", "")]
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Events", len(workflow_logs))
            with col2:
                st.metric("Companies", len(companies_processed))
            with col3:
                st.metric("Agents Run", len(agents_completed))
            with col4:
                st.metric("MCP Calls", len(mcp_calls))
            with col5:
                st.metric("MCP Responses", len(mcp_responses))
            
            # Show MCP interaction summary
            if mcp_calls or mcp_responses:
                with st.expander("🔌 MCP Server Interactions"):
                    mcp_servers = defaultdict(int)
                    for log in workflow_logs:
                        if "MCP" in log.get("📌 Action", ""):
                            details = log.get("💬 Details", "")
                            for server in ["STORE", "SEARCH", "EMAIL", "CALENDAR", "VECTOR", "OLLAMA"]:
                                if server in details.upper():
                                    mcp_servers[server] += 1
                    
                    if mcp_servers:
                        mcp_df = pd.DataFrame(
                            [(server, count) for server, count in mcp_servers.items()],
                            columns=["MCP Server", "Interactions"]
                        )
                        st.dataframe(mcp_df, hide_index=True)
        
        except requests.exceptions.Timeout:
            st.error("⏱️ Pipeline timeout - please check if Ollama is running")
        except Exception as e:
            st.error(f"Pipeline error: {str(e)}")
        finally:
            st.session_state.running = False
    
    # Show stored outputs if available
    elif st.session_state.company_outputs:
        st.subheader("📋 Previous Execution Results")
        
        company_outputs = st.session_state.company_outputs
        if company_outputs:
            # Create tabs for each company
            company_names = list(company_outputs.keys())
            if company_names:
                tabs = st.tabs([f"🏢 {name}" for name in company_names])
                
                for i, (company, outputs) in enumerate(company_outputs.items()):
                    with tabs[i]:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("### 📝 Summary")
                            if outputs.get("final_summary"):
                                st.markdown(outputs["final_summary"])
                            elif outputs.get("summary"):
                                st.markdown(outputs["summary"])
                            else:
                                st.info("No summary available")
                        
                        with col2:
                            st.markdown("### ✉️ Email Draft")
                            if outputs.get("final_email"):
                                email = outputs["final_email"]
                                if isinstance(email, dict):
                                    st.write(f"**Subject:** {email.get('subject', '')}")
                                    st.markdown(f"**Body:**\n{email.get('body', '')}")
                                else:
                                    st.markdown(email)
                            elif outputs.get("email"):
                                st.markdown(outputs["email"])
                            else:
                                st.info("No email available")

# Prospects Tab
with tab2:
    st.header("Prospects Overview")
    st.markdown("View all prospects and their current status in the pipeline")
    
    # Refresh controls
    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    try:
        prospects_data = requests.get(f"{API_BASE}/prospects").json()
        
        if prospects_data["count"] > 0:
            # Metrics row
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Prospects", prospects_data["count"])
            
            with col2:
                ready = sum(1 for p in prospects_data["prospects"] 
                           if p["status"] == "ready_for_handoff")
                st.metric("Ready for Handoff", ready)
            
            with col3:
                blocked = sum(1 for p in prospects_data["prospects"] 
                             if p["status"] in ["blocked", "dropped"])
                st.metric("Blocked/Dropped", blocked)
            
            with col4:
                scores = [p["fit_score"] for p in prospects_data["prospects"] if p["fit_score"] > 0]
                avg_score = sum(scores) / len(scores) if scores else 0
                st.metric("Avg Fit Score", f"{avg_score:.2f}")
            
            st.divider()
            
            # Prospect table with enhanced status display
            prospects_df = pd.DataFrame(prospects_data["prospects"])
            
            # Status mapping with colors and descriptions
            status_info = {
                "new": ("🆕", "New", "Just discovered"),
                "enriched": ("📚", "Enriched", "Facts gathered"),
                "contacted": ("👥", "Contacted", "Contacts identified"),
                "scored": ("📊", "Scored", "Fit score calculated"),
                "drafted": ("📝", "Drafted", "Content generated"),
                "compliant": ("✅", "Compliant", "Passed compliance"),
                "sequenced": ("📮", "Sequenced", "Email sent"),
                "ready_for_handoff": ("🎯", "Ready", "Ready for sales"),
                "dropped": ("⛔", "Dropped", "Low score"),
                "blocked": ("🚫", "Blocked", "Failed requirements")
            }
            
            # Format the dataframe
            display_data = []
            for _, row in prospects_df.iterrows():
                status = row["status"]
                icon, label, desc = status_info.get(status, ("❓", status, "Unknown"))
                
                display_data.append({
                    "Company": row["company"],
                    "Status": f"{icon} {label}",
                    "Description": desc,
                    "Fit Score": f"{row['fit_score']:.2f}" if row['fit_score'] > 0 else "N/A",
                    "Contacts": row["contacts"],
                    "Facts": row["facts"],
                    "ID": row["id"]
                })
            
            display_df = pd.DataFrame(display_data)
            
            # Show the table
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Fit Score": st.column_config.NumberColumn(
                        format="%.2f",
                        min_value=0,
                        max_value=1
                    ),
                    "Contacts": st.column_config.NumberColumn(format="%d"),
                    "Facts": st.column_config.NumberColumn(format="%d")
                }
            )
        else:
            st.info("No prospects found. Run the pipeline to generate prospects.")
    
    except Exception as e:
        st.error(f"Could not load prospects: {e}")

# Details Tab (keeping existing implementation)
with tab3:
    st.header("Prospect Details")
    st.markdown("Deep dive into individual prospect information")
    
    # Prospect selector
    col1, col2 = st.columns([3, 1])
    
    with col1:
        prospect_id = st.text_input(
            "Prospect ID",
            placeholder="Enter prospect ID (e.g., acme, techcorp, retailplus)",
            value=st.session_state.current_prospect["id"] if st.session_state.current_prospect else ""
        )
    
    with col2:
        st.write("")  # Spacer
        search_btn = st.button("🔍 Load Details", use_container_width=True)
    
    if prospect_id and (search_btn or st.session_state.current_prospect):
        try:
            data = requests.get(f"{API_BASE}/prospects/{prospect_id}", timeout=10).json()
            
            if "error" not in data:
                prospect = data["prospect"]
                thread = data.get("thread")
                # Persist current prospect so subsequent button clicks don't clear the view
                st.session_state.current_prospect = prospect
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Prospect Info")
                    st.json({
                        "Company": prospect["company"]["name"],
                        "Status": prospect["status"],
                        "Fit Score": prospect["fit_score"],
                        "Contacts": len(prospect["contacts"]),
                        "Facts": len(prospect["facts"])
                    })
                    
                    if prospect.get("summary"):
                        st.subheader("📝 Summary")
                        st.markdown(prospect["summary"])
                
                with col2:
                    if prospect.get("email_draft"):
                        st.subheader("✉️ Email Draft")
                        st.write(f"**Subject:** {prospect['email_draft']['subject']}")
                        st.markdown(prospect["email_draft"]["body"])
                    
                    if thread:
                        st.subheader("💬 Thread")
                        for msg in thread.get("messages", []):
                            with st.expander(f"{msg['direction']}: {msg['subject']}"):
                                st.write(msg["body"])
                                st.caption(f"Sent: {msg['sent_at']}")
                
                # Handoff section (persistent across reruns)
                st.subheader("📦 Handoff")
                handoff = st.session_state.handoff_packets.get(prospect_id)
                if st.button("Get Handoff Packet", key=f"handoff_{prospect_id}"):
                    try:
                        resp_h = requests.get(f"{API_BASE}/handoff/{prospect_id}", timeout=15)
                        if resp_h.status_code == 200:
                            handoff = resp_h.json()
                            st.session_state.handoff_packets[prospect_id] = handoff
                        else:
                            # Surface API error detail
                            try:
                                detail = resp_h.json().get("detail")
                            except Exception:
                                detail = resp_h.text
                            st.warning(f"Handoff not available: {detail}")
                    except Exception as e:
                        st.error(f"Could not get handoff: {e}")
                
                # Render cached handoff if available
                if handoff:
                    cols = st.columns(2)
                    with cols[0]:
                        st.markdown("**Calendar Slots**")
                        for slot in handoff.get("calendar_slots", []):
                            st.write(f"• {slot.get('start_iso','')[:16]}")
                    with cols[1]:
                        st.markdown("**Generated At**")
                        st.write(handoff.get("generated_at", "Unknown"))
                    st.markdown("**Full Packet**")
                    st.json(handoff)
                
        except Exception as e:
            st.error(f"Could not load prospect: {e}")

# Dev Tools Tab (keeping existing implementation)
with tab4:
    st.header("Developer Tools")
    
    st.subheader("🧪 Writer Streaming Test")
    
    test_company_id = st.text_input("Test Company ID", value="acme")
    
    if st.button("Test Writer Stream"):
        with st.spinner("Streaming from Writer agent..."):
            
            output_container = st.empty()
            full_text = ""
            
            try:
                response = requests.post(
                    f"{API_BASE}/writer/stream",
                    json={"company_id": test_company_id},
                    stream=True
                )
                
                for line in response.iter_lines():
                    if line:
                        try:
                            event = json.loads(line)
                            
                            if event.get("type") == "llm_token":
                                token = event["payload"].get("token", "")
                                full_text += token
                                output_container.markdown(full_text)
                            
                            elif event.get("type") == "llm_done":
                                st.success("✅ Generation complete")
                                
                                # Show final artifacts
                                if "summary" in event["payload"]:
                                    with st.expander("Final Summary"):
                                        st.markdown(event["payload"]["summary"])
                                
                                if "email" in event["payload"]:
                                    with st.expander("Final Email"):
                                        email = event["payload"]["email"]
                                        st.write(f"**Subject:** {email.get('subject', '')}")
                                        st.markdown(email.get("body", ""))
                        
                        except json.JSONDecodeError:
                            continue
            
            except Exception as e:
                st.error(f"Stream test failed: {e}")
    
    st.divider()
    
    st.subheader("📡 API Endpoints")
    
    endpoints = [
        ("GET /health", "System health check"),
        ("POST /run", "Run full pipeline (streaming)"),
        ("POST /writer/stream", "Test Writer streaming"),
        ("GET /prospects", "List all prospects"),
        ("GET /prospects/{id}", "Get prospect details"),
        ("GET /handoff/{id}", "Get handoff packet"),
        ("POST /reset", "Reset system")
    ]
    
    for endpoint, desc in endpoints:
        st.code(f"{endpoint} - {desc}")
