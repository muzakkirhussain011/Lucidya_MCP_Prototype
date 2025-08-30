# file: ui/streamlit_app.py
import streamlit as st
import requests
import json
from datetime import datetime
import asyncio
import pandas as pd

st.set_page_config(
    page_title="Lucidya MCP Prototype",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Lucidya Multi-Agent CX Platform")
st.caption("Real-time agent orchestration with Ollama streaming")

API_BASE = "http://localhost:8000"

# Sidebar
with st.sidebar:
    st.header("System Status")
    
    # Health check
    try:
        health = requests.get(f"{API_BASE}/health").json()
        
        if health["status"] == "healthy":
            st.success("✅ System Healthy")
            
            with st.expander("Details"):
                st.json(health)
        else:
            st.error("❌ System Unhealthy")
    except:
        st.error("❌ API Offline")
    
    st.divider()
    
    # System controls
    if st.button("🔄 Reset System", type="secondary"):
        with st.spinner("Resetting..."):
            try:
                result = requests.post(f"{API_BASE}/reset").json()
                st.success(f"Reset complete: {result['companies_loaded']} companies loaded")
            except Exception as e:
                st.error(f"Reset failed: {e}")

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Pipeline", "📊 Prospects", "🔍 Details", "🧪 Dev Tools"])

# Pipeline Tab
with tab1:
    st.header("Run Pipeline")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        company_ids = st.text_input(
            "Company IDs (comma-separated, or leave empty for all)",
            placeholder="acme,techcorp"
        )
    
    with col2:
        if st.button("▶️ Run Pipeline", type="primary"):
            st.session_state["running"] = True
    
    if st.session_state.get("running"):
        # Event containers
        status_container = st.container()
        token_container = st.container()
        log_container = st.container()
        
        with status_container:
            st.info("🔄 Pipeline running...")
        
        # Process stream
        logs = []
        summary_tokens = []
        email_tokens = []
        
        try:
            # Parse company IDs
            ids = None
            if company_ids:
                ids = [id.strip() for id in company_ids.split(",")]
            
            # Start streaming
            response = requests.post(
                f"{API_BASE}/run",
                json={"company_ids": ids},
                stream=True
            )
            
            with token_container:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📝 Summary Generation")
                    summary_placeholder = st.empty()
                
                with col2:
                    st.subheader("✉️ Email Draft")
                    email_placeholder = st.empty()
            
            current_summary = ""
            current_email = ""
            
            for line in response.iter_lines():
                if line:
                    try:
                        event = json.loads(line)
                        
                        # Handle different event types
                        if event["type"] == "llm_token":
                            token = event["payload"].get("token", "")
                            token_type = event["payload"].get("type", "")
                            
                            if token_type == "summary":
                                current_summary += token
                                summary_placeholder.markdown(current_summary)
                            elif token_type == "email":
                                current_email += token
                                email_placeholder.markdown(current_email)
                        
                        elif event["type"] == "llm_done":
                            # Final content
                            pass
                        
                        else:
                            # Log other events
                            logs.append({
                                "Time": event.get("ts", "")[:19],
                                "Agent": event.get("agent", ""),
                                "Type": event.get("type", ""),
                                "Message": event.get("message", "")
                            })
                    
                    except json.JSONDecodeError:
                        continue
            
            with status_container:
                st.success("✅ Pipeline complete!")
            
            # Show logs
            with log_container:
                st.subheader("📋 Event Log")
                if logs:
                    df = pd.DataFrame(logs)
                    st.dataframe(df, use_container_width=True)
        
        except Exception as e:
            st.error(f"Pipeline error: {e}")
        
        finally:
            st.session_state["running"] = False

# Prospects Tab
with tab2:
    st.header("Prospects Overview")
    
    if st.button("🔄 Refresh"):
        st.rerun()
    
    try:
        prospects = requests.get(f"{API_BASE}/prospects").json()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Prospects", prospects["count"])
        
        with col2:
            ready = sum(1 for p in prospects["prospects"] if p["status"] == "ready_for_handoff")
            st.metric("Ready for Handoff", ready)
        
        with col3:
            avg_score = sum(p["fit_score"] for p in prospects["prospects"]) / max(1, prospects["count"])
            st.metric("Avg Fit Score", f"{avg_score:.2f}")
        
        # Prospect table
        if prospects["prospects"]:
            df = pd.DataFrame(prospects["prospects"])
            
            # Status colors
            status_colors = {
                "ready_for_handoff": "🟢",
                "sequenced": "🔵",
                "compliant": "🟡",
                "drafted": "🟠",
                "dropped": "🔴",
                "blocked": "🔴"
            }
            
            df["Status"] = df["status"].apply(lambda x: f"{status_colors.get(x, '⚪')} {x}")
            
            st.dataframe(
                df[["id", "company", "Status", "fit_score", "contacts", "facts"]],
                use_container_width=True
            )
    
    except Exception as e:
        st.error(f"Could not load prospects: {e}")

# Details Tab
with tab3:
    st.header("Prospect Details")
    
    prospect_id = st.text_input("Prospect ID", placeholder="Enter prospect ID")
    
    if prospect_id:
        try:
            data = requests.get(f"{API_BASE}/prospects/{prospect_id}").json()
            
            prospect = data["prospect"]
            thread = data.get("thread")
            
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
            
            # Handoff button
            if prospect["status"] == "ready_for_handoff":
                if st.button("📦 Get Handoff Packet"):
                    try:
                        handoff = requests.get(f"{API_BASE}/handoff/{prospect_id}").json()
                        
                        st.subheader("Handoff Packet")
                        st.json(handoff)
                    except Exception as e:
                        st.error(f"Could not get handoff: {e}")
        
        except Exception as e:
            st.error(f"Could not load prospect: {e}")

# Dev Tools Tab
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