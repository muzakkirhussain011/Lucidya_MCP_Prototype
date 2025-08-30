# file: tests/test_pipeline.py
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.orchestrator import Orchestrator
from app.schema import Company, Prospect

@pytest.mark.asyncio
async def test_pipeline_with_mocked_ollama_streaming():
    """Test full pipeline with mocked Ollama streaming"""
    
    # Mock Ollama streaming responses
    mock_summary_stream = [
        {"response": "• Customer ", "done": False},
        {"response": "experience ", "done": False},
        {"response": "insights:\n", "done": False},
        {"response": "• Improve ", "done": False},
        {"response": "NPS scores", "done": True}
    ]
    
    mock_email_stream = [
        {"response": "Subject: ", "done": False},
        {"response": "Improve Your CX\n", "done": False},
        {"response": "Body: Dear ", "done": False},
        {"response": "team,\n", "done": False},
        {"response": "Let's discuss.", "done": True}
    ]
    
    # Mock aiohttp session
    mock_response = AsyncMock()
    
    async def mock_content_generator(stream_data):
        for item in stream_data:
            yield json.dumps(item).encode() + b"\n"
    
    # Setup orchestrator with mocked dependencies
    orchestrator = Orchestrator()
    
    # Mock MCP registry
    mock_store = AsyncMock()
    mock_search = AsyncMock()
    mock_email = AsyncMock()
    mock_calendar = AsyncMock()
    
    orchestrator.mcp.get_store_client = Mock(return_value=mock_store)
    orchestrator.mcp.get_search_client = Mock(return_value=mock_search)
    orchestrator.mcp.get_email_client = Mock(return_value=mock_email)
    orchestrator.mcp.get_calendar_client = Mock(return_value=mock_calendar)
    
    # Setup mock returns
    mock_store.save_prospect.return_value = None
    mock_store.save_fact.return_value = None
    mock_store.save_contact.return_value = None
    mock_store.check_suppression.return_value = False
    mock_store.save_handoff.return_value = None
    
    mock_search.query.return_value = [
        {"text": "Test fact", "source": "test", "confidence": 0.8}
    ]
    
    mock_email.send.return_value = {
        "thread_id": "thread-123",
        "message_id": "msg-123"
    }
    
    mock_email.get_thread.return_value = AsyncMock(
        id="thread-123",
        prospect_id="acme",
        messages=[]
    )
    
    mock_calendar.suggest_slots.return_value = [
        {"start_iso": "2024-01-15T14:00:00", "end_iso": "2024-01-15T14:30:00"}
    ]
    
    mock_calendar.generate_ics.return_value = "BEGIN:VCALENDAR..."
    
    # Mock the Writer's streaming with aiohttp
    with patch('aiohttp.ClientSession') as mock_session_class:
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        
        # Setup response mocks for both summary and email generation
        summary_response = AsyncMock()
        summary_response.content = mock_content_generator(mock_summary_stream)
        
        email_response = AsyncMock()
        email_response.content = mock_content_generator(mock_email_stream)
        
        # Configure post to return different responses
        responses = [summary_response, email_response]
        mock_session.post.return_value.__aenter__.side_effect = responses
        
        # Run pipeline
        events = []
        async for event in orchestrator.run_pipeline(["acme"]):
            events.append(event)
        
        # Verify events were generated
        assert len(events) > 0
        
        # Check for key event types
        event_types = [e["type"] for e in events]
        assert "agent_start" in event_types
        assert "agent_end" in event_types
        assert "llm_token" in event_types
        assert "llm_done" in event_types
        
        # Verify LLM tokens were streamed
        token_events = [e for e in events if e["type"] == "llm_token"]
        assert len(token_events) > 0
        
        # Check that summary tokens were generated
        summary_tokens = [e for e in token_events if e.get("payload", {}).get("type") == "summary"]
        email_tokens = [e for e in token_events if e.get("payload", {}).get("type") == "email"]
        
        assert len(summary_tokens) > 0, "Should have summary tokens"
        assert len(email_tokens) > 0, "Should have email tokens"
        
        # Verify pipeline completed successfully
        done_events = [e for e in events if e["type"] == "llm_done"]
        assert len(done_events) > 0
        
        # Check final prospect state
        if done_events:
            final_prospect = done_events[0]["payload"].get("prospect")
            if final_prospect:
                assert final_prospect.summary is not None
                assert final_prospect.email_draft is not None

@pytest.mark.asyncio
async def test_pipeline_dropped_prospect():
    """Test that low-scoring prospects are dropped"""
    
    orchestrator = Orchestrator()
    
    # Mock dependencies
    mock_store = AsyncMock()
    orchestrator.mcp.get_store_client = Mock(return_value=mock_store)
    
    # Create a prospect that will score low
    company = Company(
        id="lowscore",
        name="Low Score Inc",
        domain="lowscore.com",
        industry="Unknown",
        size=10,  # Too small
        pains=[]  # No pain points
    )
    
    # Mock the hunter to return this prospect
    orchestrator.hunter.run = AsyncMock(return_value=[
        Prospect(
            id="lowscore",
            company=company,
            status="new",
            facts=[],
            fit_score=0.1  # Below threshold
        )
    ])
    
    orchestrator.enricher.run = AsyncMock(side_effect=lambda p: p)
    orchestrator.contactor.run = AsyncMock(side_effect=lambda p: p)
    
    # Scorer should drop it
    async def mock_scorer_run(prospect):
        prospect.status = "dropped"
        prospect.dropped_reason = "Low fit score: 0.10"
        return prospect
    
    orchestrator.scorer.run = AsyncMock(side_effect=mock_scorer_run)
    
    # Collect events
    events = []
    async for event in orchestrator.run_pipeline(["lowscore"]):
        events.append(event)
    
    # Verify prospect was dropped
    scorer_events = [e for e in events if e["agent"] == "scorer"]
    assert any("Dropped" in e.get("message", "") for e in scorer_events)
    
    # Should not have writer events
    writer_events = [e for e in events if e["agent"] == "writer"]
    assert len(writer_events) == 0