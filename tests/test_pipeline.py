# file: tests/test_pipeline.py
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, mock_open
from app.orchestrator import Orchestrator
from app.schema import Company, Prospect
from pathlib import Path
import asyncio

@pytest.mark.asyncio
async def test_pipeline_happy_path():
    """Test full pipeline execution without streaming details"""
    
    # Create a test company in mock data
    test_company = {
        "id": "test",
        "name": "Test Co",
        "domain": "test.com",
        "industry": "SaaS",
        "size": 100,
        "pains": ["Low NPS scores"],
        "notes": ["Growing company"]
    }
    
    # Mock file operations for companies.json
    with patch('builtins.open', mock_open(read_data=json.dumps([test_company]))):
        # Mock MCP registry at module level
        with patch('app.orchestrator.MCPRegistry') as MockMCPRegistry:
            mock_mcp = Mock()
            MockMCPRegistry.return_value = mock_mcp
            
            # Mock store client
            mock_store = AsyncMock()
            mock_store.save_prospect = AsyncMock(return_value=None)
            mock_store.save_company = AsyncMock(return_value=None)
            mock_store.save_fact = AsyncMock(return_value=None)
            mock_store.save_contact = AsyncMock(return_value=None)
            mock_store.save_handoff = AsyncMock(return_value=None)
            mock_store.check_suppression = AsyncMock(return_value=False)
            mock_store.list_contacts_by_domain = AsyncMock(return_value=[])
            
            # Mock search client
            mock_search = AsyncMock()
            mock_search.query = AsyncMock(return_value=[
                {
                    "text": "Test Co focuses on customer experience",
                    "source": "Industry Report",
                    "confidence": 0.85
                }
            ])
            
            # Mock email client
            mock_email = AsyncMock()
            mock_email.send = AsyncMock(return_value={"thread_id": "test-thread-123", "message_id": "msg-456", "prospect_id": "test"})
            mock_email.get_thread = AsyncMock(return_value={
                "id": "test-thread-123",
                "prospect_id": "test",
                "messages": [{
                    "id": "msg-456",
                    "thread_id": "test-thread-123",
                    "direction": "outbound",
                    "subject": "Test Subject",
                    "body": "Test Body",
                    "sent_at": "2024-01-01T00:00:00"
                }]
            })
            
            # Mock calendar client
            mock_calendar = AsyncMock()
            mock_calendar.suggest_slots = AsyncMock(return_value=[
                {"start_iso": "2024-01-02T14:00:00", "end_iso": "2024-01-02T14:30:00"}
            ])
            mock_calendar.generate_ics = AsyncMock(return_value="BEGIN:VCALENDAR...")
            
            # Configure mock MCP
            mock_mcp.get_store_client.return_value = mock_store
            mock_mcp.get_search_client.return_value = mock_search
            mock_mcp.get_email_client.return_value = mock_email
            mock_mcp.get_calendar_client.return_value = mock_calendar
            
            # Mock Path for footer file
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'read_text', return_value="\n---\nTest Footer"):
                    # Mock vector retriever
                    with patch('agents.writer.Retriever') as MockRetriever:
                        mock_retriever = Mock()
                        mock_retriever.retrieve.return_value = [
                            {"text": "Relevant fact 1", "score": 0.9}
                        ]
                        MockRetriever.return_value = mock_retriever
                        
                        # Mock requests for Ollama (fallback in Writer)
                        with patch('agents.writer.aiohttp.ClientSession') as MockSession:
                            # Create a mock that fails, triggering the fallback in Writer
                            mock_session = AsyncMock()
                            mock_session.post.side_effect = Exception("Connection failed")
                            MockSession.return_value.__aenter__.return_value = mock_session
                            
                            # Create orchestrator
                            orchestrator = Orchestrator()
                            
                            # Collect all events
                            events = []
                            async for event in orchestrator.run_pipeline(["test"]):
                                events.append(event)
                            
                            # Verify key events occurred
                            event_types = [e.get("type") for e in events]
                            
                            # Should have agent events
                            assert "agent_start" in event_types
                            assert "agent_end" in event_types
                            
                            # Should have MCP interactions
                            assert "mcp_call" in event_types
                            assert "mcp_response" in event_types
                            
                            # Check for either successful completion or policy block
                            # (depends on whether email draft was generated via fallback)
                            assert "llm_done" in event_types or "policy_block" in event_types
                            
                            # Verify core MCP operations were attempted
                            assert mock_store.save_prospect.called
                            assert mock_search.query.called

@pytest.mark.asyncio
async def test_pipeline_compliance_block():
    """Test that compliance violations block the pipeline"""
    
    test_company = {
        "id": "blocked-test",
        "name": "Blocked Co",
        "domain": "blocked.com",
        "industry": "SaaS",
        "size": 100,
        "pains": ["Test pain"],
        "notes": []
    }
    
    with patch('builtins.open', mock_open(read_data=json.dumps([test_company]))):
        with patch('app.orchestrator.MCPRegistry') as MockMCPRegistry:
            mock_mcp = Mock()
            MockMCPRegistry.return_value = mock_mcp
            
            # Mock store with suppressed domain
            mock_store = AsyncMock()
            mock_store.save_prospect = AsyncMock(return_value=None)
            mock_store.save_fact = AsyncMock(return_value=None)
            mock_store.save_contact = AsyncMock(return_value=None)
            
            # This will make the domain suppressed
            async def check_suppression(type, value):
                if type == "domain" and value == "blocked.com":
                    return True
                if type == "email" and "blocked.com" in value:
                    return True
                return False
            
            mock_store.check_suppression = AsyncMock(side_effect=check_suppression)
            mock_store.list_contacts_by_domain = AsyncMock(return_value=[])
            
            # Mock search
            mock_search = AsyncMock()
            mock_search.query = AsyncMock(return_value=[])
            
            # Mock email and calendar
            mock_email = AsyncMock()
            mock_calendar = AsyncMock()
            
            mock_mcp.get_store_client.return_value = mock_store
            mock_mcp.get_search_client.return_value = mock_search
            mock_mcp.get_email_client.return_value = mock_email
            mock_mcp.get_calendar_client.return_value = mock_calendar
            
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'read_text', return_value="\n---\nTest Footer"):
                    with patch('agents.writer.Retriever') as MockRetriever:
                        mock_retriever = Mock()
                        mock_retriever.retrieve.return_value = []
                        MockRetriever.return_value = mock_retriever
                        
                        orchestrator = Orchestrator()
                        
                        events = []
                        async for event in orchestrator.run_pipeline(["blocked-test"]):
                            events.append(event)
                        
                        # Should have dropped or blocked due to suppression
                        messages = [str(e.get("message", "")).lower() for e in events]
                        reasons = [str(e.get("payload", {}).get("reason", "")).lower() for e in events]
                        all_text = " ".join(messages + reasons)
                        
                        assert "suppressed" in all_text or "dropped" in all_text or "blocked" in all_text, \
                            f"Should have suppression/dropped/blocked message"

@pytest.mark.asyncio
async def test_pipeline_scorer_drop():
    """Test that low scores drop prospects"""
    
    test_company = {
        "id": "low-score",
        "name": "Small Co",
        "domain": "small.com",
        "industry": "Unknown",  # Low value industry
        "size": 10,  # Too small
        "pains": [],  # No pains
        "notes": []
    }
    
    with patch('builtins.open', mock_open(read_data=json.dumps([test_company]))):
        with patch('app.orchestrator.MCPRegistry') as MockMCPRegistry:
            mock_mcp = Mock()
            MockMCPRegistry.return_value = mock_mcp
            
            mock_store = AsyncMock()
            mock_store.save_prospect = AsyncMock(return_value=None)
            mock_store.save_fact = AsyncMock(return_value=None)
            mock_store.save_contact = AsyncMock(return_value=None)
            mock_store.check_suppression = AsyncMock(return_value=False)
            mock_store.list_contacts_by_domain = AsyncMock(return_value=[])
            
            mock_search = AsyncMock()
            mock_search.query = AsyncMock(return_value=[])
            
            mock_email = AsyncMock()
            mock_calendar = AsyncMock()
            
            mock_mcp.get_store_client.return_value = mock_store
            mock_mcp.get_search_client.return_value = mock_search
            mock_mcp.get_email_client.return_value = mock_email
            mock_mcp.get_calendar_client.return_value = mock_calendar
            
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'read_text', return_value="\n---\nTest Footer"):
                    with patch('agents.writer.Retriever') as MockRetriever:
                        mock_retriever = Mock()
                        mock_retriever.retrieve.return_value = []
                        MockRetriever.return_value = mock_retriever
                        
                        orchestrator = Orchestrator()
                        
                        events = []
                        async for event in orchestrator.run_pipeline(["low-score"]):
                            events.append(event)
                        
                        # Check for drop message in events
                        found_drop = False
                        for event in events:
                            message = str(event.get("message", "")).lower()
                            reason = str(event.get("payload", {}).get("reason", "")).lower()
                            status = str(event.get("payload", {}).get("status", "")).lower()
                            
                            if "dropped" in message or "dropped" in reason or "dropped" in status or "low fit score" in message or "low fit score" in reason:
                                found_drop = True
                                break
                        
                        assert found_drop, f"Should have found drop message"