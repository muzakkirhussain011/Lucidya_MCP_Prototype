from __future__ import annotations
from typing import Iterator, Tuple
from app.tools.llm import ollama_generate, ollama_generate_markdown_stream
from app.domain_models import Company, Person

SYSTEM_SUMMARY = (
    "You are a B2B analyst. Generate a bullet list of 5-8 points about customer experience "
    "opportunities and challenges for the company. Focus on actionable insights. "
    "Output ONLY bullet points starting with '- '. No headers or other text."
)

SYSTEM_OUTREACH = (
    "You are a professional SDR at Lucidya, a CX analytics company. Write clear, concise emails. "
    "Always sign as 'The Lucidya Team'. Keep it professional and focused on value."
)

class WriterAgent:
    sender_email = "team@lucidya.example"

    def internal_summary_stream(self, enrichment_text: str) -> Iterator[str]:
        """Stream internal summary as markdown bullets."""
        prompt = enrichment_text + "\n\nGenerate the bullet points now:"
        
        try:
            for chunk in ollama_generate_markdown_stream(prompt, system=SYSTEM_SUMMARY, temperature=0.3):
                yield chunk
        except Exception as e:
            # Fallback to basic bullets if streaming fails
            yield "- Customer experience analytics could provide valuable insights\n"
            yield "- Opportunity to improve response times and satisfaction scores\n"
            yield "- Multi-channel support integration would benefit operations\n"
            yield "- Real-time monitoring could help identify issues faster\n"
            yield "- Automated reporting would save time for CX teams\n"

    def outreach_stream(self, company: Company, person: Person) -> Iterator[Tuple]:
        """Stream email composition for outreach."""
        # Generate subject
        try:
            subject = ollama_generate(
                f"Write a short compelling email subject for CX analytics outreach to {company.name}. "
                f"Recipient is {person.role}. Maximum 10 words. Do not use quotes.",
                system=SYSTEM_OUTREACH, 
                temperature=0.4
            )
        except:
            subject = f"Enhance {company.name}'s Customer Experience with Analytics"
        
        yield ("subject", subject)

        # Stream body
        body_prompt = f"""
Company: {company.name}
Industry: {company.industry}
Recipient: {person.name} - {person.role}

Write a 120-180 word email offering Lucidya's CX analytics platform.
Include 3-4 short bullet points about specific benefits.
Sign as 'The Lucidya Team'.
Be professional and value-focused.
"""
        
        try:
            body_parts = []
            for chunk in ollama_generate_markdown_stream(body_prompt, system=SYSTEM_OUTREACH, temperature=0.4):
                body_parts.append(chunk)
                yield ("body_delta", chunk)
            
            final_body = "".join(body_parts)
            if not final_body.strip():
                raise Exception("Empty body generated")
                
        except Exception as e:
            # Fallback email template
            final_body = f"""Dear {person.name},

We hope this message finds you well. At Lucidya, we specialize in helping {company.industry} companies enhance their customer experience through advanced analytics.

We've identified several opportunities where {company.name} could benefit:

- Real-time sentiment analysis across all customer touchpoints
- Automated insights to reduce response times and improve satisfaction
- Unified dashboard for monitoring customer experience metrics
- AI-powered recommendations for proactive issue resolution

Our platform has helped similar companies in {company.region} achieve significant improvements in NPS scores and operational efficiency.

Would you be interested in a brief discussion about how Lucidya could support {company.name}'s CX initiatives?

Best regards,
The Lucidya Team"""
            
            # Stream the fallback
            for line in final_body.split('\n'):
                if line:
                    yield ("body_delta", line + '\n')

        # Final complete version
        yield ("final", subject, final_body)