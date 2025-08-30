# file: tests/test_dedupe.py
import pytest
from unittest.mock import Mock, AsyncMock
from agents.contactor import Contactor
from app.schema import Prospect, Company, Contact

@pytest.mark.asyncio
async def test_contact_deduplication():
    """Test that Contactor dedupes emails properly"""
    
    # Mock MCP registry
    mock_mcp = Mock()
    mock_store = AsyncMock()
    mock_mcp.get_store_client.return_value = mock_store
    
    # Setup existing contacts
    existing_contacts = [
        Contact(
            id="existing-1",
            name="Existing Contact",
            email="ceo@acme.com",
            title="CEO",
            prospect_id="other"
        )
    ]
    
    mock_store.list_contacts_by_domain.return_value = existing_contacts
    mock_store.check_suppression.return_value = False
    mock_store.save_contact.return_value = None
    mock_store.save_prospect.return_value = None
    
    # Create test prospect
    company = Company(
        id="acme",
        name="Acme Corp",
        domain="acme.com",
        industry="SaaS",
        size=100,
        pains=[]
    )
    
    prospect = Prospect(
        id="test-prospect",
        company=company,
        status="enriched"
    )
    
    # Run contactor
    contactor = Contactor(mock_mcp)
    result = await contactor.run(prospect)
    
    # Verify deduplication
    assert len(result.contacts) > 0
    
    # Check that ceo@acme.com was not added again
    emails = [c.email for c in result.contacts]
    assert "ceo@acme.com" not in emails
    
    # Verify store was called correctly
    mock_store.list_contacts_by_domain.assert_called_with("acme.com")

@pytest.mark.asyncio
async def test_domain_deduplication():
    """Test that same-domain contacts are properly deduplicated"""
    
    mock_mcp = Mock()
    mock_store = AsyncMock()
    mock_mcp.get_store_client.return_value = mock_store
    
    # Multiple existing contacts from same domain
    existing_contacts = [
        Contact(id="1", name="Contact 1", email="vp@acme.com", 
                title="VP", prospect_id="other"),
        Contact(id="2", name="Contact 2", email="director@acme.com",
                title="Director", prospect_id="other")
    ]
    
    mock_store.list_contacts_by_domain.return_value = existing_contacts
    mock_store.check_suppression.return_value = False
    mock_store.save_contact.return_value = None
    mock_store.save_prospect.return_value = None
    
    company = Company(
        id="acme",
        name="Acme Corp",
        domain="acme.com",
        industry="SaaS",
        size=500,
        pains=[]
    )
    
    prospect = Prospect(
        id="test-prospect",
        company=company,
        status="enriched"
    )
    
    contactor = Contactor(mock_mcp)
    result = await contactor.run(prospect)
    
    # Should generate new contacts but not duplicate existing
    emails = [c.email for c in result.contacts]
    assert "vp@acme.com" not in emails
    assert "director@acme.com" not in emails
    
    # Should have some contacts though
    assert len(result.contacts) > 0