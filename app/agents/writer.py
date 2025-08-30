from __future__ import annotations
from typing import Iterator, Tuple
from app.tools.llm import ollama_generate, ollama_generate_markdown_stream
from app.domain_models import Company, Person

SYSTEM_SUMMARY = (
    "You are a B2B analyst. Read the provided context and output a **pure Markdown bullet list**:\n"
    "- EXACTLY 5–8 bullets.\n"
    "- Each bullet MUST start with '- ' and be on its own line.\n"
    "- Do not put multiple bullets on one line.\n"
    "- Keep it concise and business friendly."
)

SYSTEM_OUTREACH = (
    "You are a professional SDR at a CX analytics company. Write clear, concise emails. "
    "NEVER use the user's name as sender; sign as 'The Lucidya Team'. Use Markdown."
)

class WriterAgent:
    sender_email = "team@lucidya.example"

    def internal_summary_stream(self, enrichment_text: str) -> Iterator[str]:
        prompt = (
            f"{enrichment_text}\n\n"
            "Now produce ONLY the bullet list. No headings before or after. No prose outside bullets."
        )
        for chunk in ollama_generate_markdown_stream(prompt, system=SYSTEM_SUMMARY, temperature=0.2):
            yield chunk

    def outreach_stream(self, company: Company, person: Person) -> Iterator[Tuple[str, str]]:
        subject = ollama_generate(
            f"Write a short compelling subject for a CX analytics outreach to {company.name} (recipient role: {person.role}).",
            system=SYSTEM_OUTREACH, temperature=0.4
        )
        yield ("subject", subject)

        body_prompt = (
            f"Company: {company.name}\nRecipient: {person.name} – {person.role}\n"
            f"Write a 120-180 word email with 3-5 short bullets on how Lucidya can help. "
            f"Do not use the user's name; sign as 'The Lucidya Team'."
        )
        for chunk in ollama_generate_markdown_stream(body_prompt, system=SYSTEM_OUTREACH, temperature=0.4):
            yield ("body_delta", chunk)

        final_body = ollama_generate(body_prompt + "\n\nNow output the full email again, polished.", system=SYSTEM_OUTREACH, temperature=0.3)
        yield ("final", subject, final_body)
