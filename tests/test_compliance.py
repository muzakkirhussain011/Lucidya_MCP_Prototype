# file: tests/test_compliance.py
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
from agents.compliance import Compliance
from app.schema import Prospect, Company, Contact

@pytest.mark.asyncio
async def test_footer_insertion():
    """Test that compliance agent inserts footer"""
    
    mock_mcp = Mock()
    mock_store = AsyncMock()
    mock_mcp.get_store_client.return_value = mock_store
    mock_store.check_suppression.return_value = False
    mock_store.save_prospect.return_value = None
    
    company = Company(
        id="test",
        name="Test Co",
        domain="test.com",
        industry="SaaS",
        size=100,
        pains=[]
    )
    
    prospect = Prospect(
        id="test-prospect",
        company=company,
        status="drafted",
        email_draft={
            "subject": "Test Subject",
            "body": "This is a test email body."
        },
        contacts=[
            Contact(
                id="c1",
                name="Test Contact",
                email="test@test.com",
                title="CEO",
                prospect_id="test-prospect"
            )
        ]
    )
    
    compliance = Compliance(mock_mcp)
    result = await compliance.run(prospect)
    
    # Check footer was added
    assert "Lucidya Inc." in result.email_draft["body"]
    assert "unsubscribe" in result.email_draft["body"].lower()
    assert result.status == "compliant"

@pytest.mark.asyncio
async def test_suppression_enforcement():
    """Test that suppressed emails are blocked"""
    
    mock_mcp = Mock()
    mock_store = AsyncMock()
    mock_mcp.get_store_client.return_value = mock_store
    
    # Suppress the email
    mock_store.check_suppression.side_effect = lambda type, value: (
        True if type == "email" and value == "blocked@test.com" else False
    )
    mock_store.save_prospect.return_value = None
    
    company = Company(
        id="test",
        name="Test Co",
        domain="test.com",
        industry="SaaS",
        size=100,
        pains=[]
    )
    
    prospect = Prospect(
        id="test-prospect",
        company=company,
        status="drafted",
        email_draft={
            "subject": "Test",
            "body": "Test body"
        },
        contacts=[
            Contact(
                id="c1",
                name="Blocked Contact",
                email="blocked@test.com",
                title="CEO",
                prospect_id="test-prospect"
            )
        ]
    )
    
    compliance = Compliance(mock_mcp)
    result = await compliance.run(prospect)
    
    # Should be blocked
    assert result.status == "blocked"
    assert "suppressed" in result.dropped_reason.lower()

@pytest.mark.asyncio
async def test_unverifiable_claims_blocking():
    """Test that unverifiable claims are caught"""
    
    mock_mcp = Mock()
    mock_store = AsyncMock()
    mock_mcp.get_store_client.return_value = mock_store
    mock_store.check_suppression.return_value = False
    mock_store.save_prospect.return_value = None
    
    company = Company(
        id="test",
        name="Test Co",
        domain="test.com",
        industry="SaaS",
        size=100,
        pains=[]
    )
    
    prospect = Prospect(
        id="test-prospect",
        company=company,
        status="drafted",
        email_draft={
            "subject": "Guaranteed Results",
            "body": "We guarantee 100% improvement with no risk!"
        },
        contacts=[
            Contact(
                id="c1",
                name="Test",
                email="test@test.com",
                title="CEO",
                prospect_id="test-prospect"
            )
        ]
    )
    
    compliance = Compliance(mock_mcp)
    result = await compliance.run(prospect)
    
    # Should be blocked for unverifiable claims
    assert result.status == "blocked"
    assert "guaranteed" in result.dropped_reason.lower() or "100%" in result.dropped_reason.lower()