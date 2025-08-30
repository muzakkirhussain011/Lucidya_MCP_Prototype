# file: agents/writer.py
import json
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
        relevant_facts = self.retriever.retrieve(prospect.company.id, k=5)
        
        # Build context
        context = f"""
Company: {prospect.company.name}
Industry: {prospect.company.industry}
Size: {prospect.company.size} employees
Domain: {prospect.company.domain}

Pain Points:
{chr(10).join(f'- {pain}' for pain in prospect.company.pains)}

Key Facts:
{chr(10).join(f'- {fact["text"]} (confidence: {fact.get("score", 0.7):.2f})' for fact in relevant_facts[:3])}
"""
        
        # Generate summary first
        summary_prompt = f"""{context}

Generate a brief bullet-point summary of key insights about this company's customer experience opportunities. 
Format: 3-5 bullets, each starting with "•". Be specific and actionable."""
        
        summary_text = ""
        
        async with aiohttp.ClientSession() as session:
            # Summary generation
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": summary_prompt,
                    "stream": True
                }
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                token = chunk["response"]
                                summary_text += token
                                yield log_event("writer", token, "llm_token", 
                                              {"type": "summary", "token": token})
                            
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        
        # Generate email
        email_prompt = f"""{context}

Write a personalized outreach email to the head of customer experience.
Requirements:
- Subject line (brief and compelling)
- Body: 150-180 words
- Professional but friendly tone
- Focus on their specific industry challenges
- One clear call-to-action
- No exaggerated claims

Format response as:
Subject: [subject line]
Body: [email body]"""
        
        email_text = ""
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": email_prompt,
                    "stream": True
                }
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            chunk = json.loads(line)
                            if "response" in chunk:
                                token = chunk["response"]
                                email_text += token
                                yield log_event("writer", token, "llm_token",
                                              {"type": "email", "token": token})
                            
                            if chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        
        # Parse email
        email_parts = {"subject": "", "body": ""}
        if "Subject:" in email_text and "Body:" in email_text:
            parts = email_text.split("Body:")
            email_parts["subject"] = parts[0].replace("Subject:", "").strip()
            email_parts["body"] = parts[1].strip()
        else:
            # Fallback
            email_parts["subject"] = f"Improve {prospect.company.name}'s Customer Experience"
            email_parts["body"] = email_text or "I'd like to discuss how we can help improve your customer experience."
        
        # Update prospect
        prospect.summary = summary_text
        prospect.email_draft = email_parts
        prospect.status = "drafted"
        await self.store.save_prospect(prospect)
        
        # Emit completion event
        yield log_event("writer", "Generation complete", "llm_done", 
                       {"prospect": prospect, "summary": summary_text, "email": email_parts})
    
    async def run(self, prospect: Prospect) -> Prospect:
        """Non-streaming version for compatibility"""
        async for event in self.run_streaming(prospect):
            if event["type"] == "llm_done":
                return event["payload"]["prospect"]
        return prospect