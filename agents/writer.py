# file: agents/writer.py
import json
import re
import aiohttp
from typing import AsyncGenerator
from app.schema import Prospect
from app.config import OLLAMA_BASE_URL, MODEL_NAME
from app.logging_utils import log_event
from vector.retriever import Retriever

class Writer:
    """Generates outreach content with Ollama streaming"""
    
    def __init__(self, mcp_registry):
        self.mcp = mcp_registry
        self.store = mcp_registry.get_store_client()
        self.retriever = Retriever()
    
    async def run_streaming(self, prospect: Prospect) -> AsyncGenerator[dict, None]:
        """Generate content with streaming tokens"""
        
        # Get relevant facts from vector store
        try:
            relevant_facts = self.retriever.retrieve(prospect.company.id, k=5)
        except:
            relevant_facts = []
        
        # Build comprehensive context
        context = f"""
COMPANY PROFILE:
Name: {prospect.company.name}
Industry: {prospect.company.industry}
Size: {prospect.company.size} employees
Domain: {prospect.company.domain}

KEY CHALLENGES:
{chr(10).join(f'• {pain}' for pain in prospect.company.pains)}

BUSINESS CONTEXT:
{chr(10).join(f'• {note}' for note in prospect.company.notes) if prospect.company.notes else '• No additional notes'}

RELEVANT INSIGHTS:
{chr(10).join(f'• {fact["text"]} (confidence: {fact.get("score", 0.7):.2f})' for fact in relevant_facts[:3]) if relevant_facts else '• Industry best practices suggest focusing on customer experience improvements'}
"""
        
        # Generate comprehensive summary first
        summary_prompt = f"""{context}

Generate a comprehensive bullet-point summary for {prospect.company.name} that includes:
1. Company overview (industry, size)
2. Main challenges they face
3. Specific opportunities for improvement
4. Recommended actions

Format: Use 5-7 bullets, each starting with "•". Be specific and actionable.
Include the industry and size context in your summary."""
        
        summary_text = ""
        
        # Emit company header first
        yield log_event("writer", f"Generating content for {prospect.company.name}", "company_start", 
                       {"company": prospect.company.name, 
                        "industry": prospect.company.industry,
                        "size": prospect.company.size})
        
        async with aiohttp.ClientSession() as session:
            # Summary generation
            try:
                async with session.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": MODEL_NAME,
                        "prompt": summary_prompt,
                        "stream": True,
                        "think": False
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    async for line in response.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "response" in chunk:
                                    token = chunk["response"]
                                    summary_text += token
                                    yield log_event(
                                        "writer",
                                        token,
                                        "llm_token",
                                        {
                                            "type": "summary",
                                            "token": token,
                                            "prospect_id": prospect.id,
                                            "company_id": prospect.company.id,
                                            "company_name": prospect.company.name,
                                        },
                                    )
                                
                                if chunk.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                summary_text = f"""• {prospect.company.name} is a {prospect.company.industry} company with {prospect.company.size} employees
• Main challenge: {prospect.company.pains[0] if prospect.company.pains else 'Customer experience improvement'}
• Opportunity: Implement modern CX solutions to improve customer satisfaction
• Recommended action: Schedule a consultation to discuss specific needs"""
                yield log_event("writer", f"Summary generation failed, using default: {e}", "llm_error")
        
        # Generate personalized email
        # If we have a contact, instruct the greeting explicitly
        greeting_hint = ""
        if prospect.contacts:
            first = (prospect.contacts[0].name or "").split()[0]
            if first:
                greeting_hint = f"Use this greeting exactly at the start: 'Hi {first},'\n"

        email_prompt = f"""{context}

Company Summary:
{summary_text}

Write a personalized outreach email from Lucidya to leaders at {prospect.company.name}.
{greeting_hint}
Requirements:
- Subject line that mentions their company name and industry
- Body: 150-180 words, professional and friendly
- Make it clear the sender is Lucidya (use "we" and "our" as Lucidya)
- Reference their specific industry ({prospect.company.industry}) and size ({prospect.company.size} employees)
- Clearly connect their challenges to Lucidya's capabilities
- One clear call-to-action to schedule a short conversation or demo next week
- Do not write as if the email is from the company to Lucidya
- No exaggerated claims
- Sign off as: "The Lucidya Team"

Format response exactly as:
Subject: [subject line]
Body: [email body]
"""
        
        email_text = ""
        
        # Emit email generation start
        yield log_event("writer", f"Generating email for {prospect.company.name}", "email_start",
                       {"company": prospect.company.name})
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": MODEL_NAME,
                        "prompt": email_prompt,
                        "stream": True,
                        "think": False
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    async for line in response.content:
                        if line:
                            try:
                                chunk = json.loads(line)
                                if "response" in chunk:
                                    token = chunk["response"]
                                    email_text += token
                                    yield log_event(
                                        "writer",
                                        token,
                                        "llm_token",
                                        {
                                            "type": "email",
                                            "token": token,
                                            "prospect_id": prospect.id,
                                            "company_id": prospect.company.id,
                                            "company_name": prospect.company.name,
                                        },
                                    )
                                
                                if chunk.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                email_text = f"""Subject: Improve {prospect.company.name}'s Customer Experience

Body: Dear {prospect.company.name} team,

As a {prospect.company.industry} company with {prospect.company.size} employees, you face unique customer experience challenges. We understand that {prospect.company.pains[0] if prospect.company.pains else 'improving customer satisfaction'} is a priority for your organization.

Our platform has helped similar companies in the {prospect.company.industry} industry improve their customer experience metrics by up to 30%. We'd love to discuss how we can help {prospect.company.name} achieve similar results.

Would you be available for a brief call next week to explore how we can address your specific needs?

Best regards,
Lucidya Team"""
                yield log_event("writer", f"Email generation failed, using default: {e}", "llm_error")
        
        # Parse email
        email_parts = {"subject": "", "body": ""}
        if "Subject:" in email_text and "Body:" in email_text:
            parts = email_text.split("Body:")
            email_parts["subject"] = parts[0].replace("Subject:", "").strip()
            email_parts["body"] = parts[1].strip()
        else:
            # Fallback with company details
            email_parts["subject"] = f"Transform {prospect.company.name}'s Customer Experience"
            email_parts["body"] = email_text or f"""Dear {prospect.company.name} team,

As a leading {prospect.company.industry} company with {prospect.company.size} employees, we know you're focused on delivering exceptional customer experiences.

We'd like to discuss how our platform can help address your specific challenges and improve your customer satisfaction metrics.

Best regards,
Lucidya Team"""

        # Replace any placeholder tokens like [Team Name] with actual contact name if available
        if prospect.contacts:
            contact_name = prospect.contacts[0].name
            if email_parts.get("subject"):
                email_parts["subject"] = re.sub(r"\[[^\]]+\]", contact_name, email_parts["subject"])
            if email_parts.get("body"):
                email_parts["body"] = re.sub(r"\[[^\]]+\]", contact_name, email_parts["body"])

        # Update prospect
        prospect.summary = f"**{prospect.company.name} ({prospect.company.industry}, {prospect.company.size} employees)**\n\n{summary_text}"
        prospect.email_draft = email_parts
        prospect.status = "drafted"
        await self.store.save_prospect(prospect)
        
        # Emit completion event with company info
        yield log_event(
            "writer",
            f"Generation complete for {prospect.company.name}",
            "llm_done",
            {
                "prospect": prospect,
                "summary": prospect.summary,
                "email": email_parts,
                "company_name": prospect.company.name,
                "prospect_id": prospect.id,
                "company_id": prospect.company.id,
            },
        )
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Non-streaming version for compatibility"""
        async for event in self.run_streaming(prospect):
            if event["type"] == "llm_done":
                return event["payload"]["prospect"]
        return prospect
