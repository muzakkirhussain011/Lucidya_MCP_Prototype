from datetime import datetime
from app.domain_models import Company

class DiscoveryAgent:
    def seed(self) -> list[Company]:
        """
        Use real-world companies with real domains so search/retrieval returns live content.
        Sizes are approximate for demo purposes only; the domain/website are accurate.
        """
        now = datetime.utcnow()
        return [
            Company(
                id="c1",
                name="stc (Saudi Telecom Company)",
                domain="stc.com.sa",
                industry="Telecommunications",
                size=20000,
                region="KSA",
                website="https://www.stc.com.sa/",
                challenges=[
                    "High inbound contact volume",
                    "Omnichannel monitoring across Arabic/English",
                    "Reducing average handling time (AHT)",
                ],
                tech_stack=["Salesforce", "WhatsApp Business API", "Genesys"],
                last_enriched_at=now,
            ),
            Company(
                id="c2",
                name="First Abu Dhabi Bank (FAB)",
                domain="bankfab.com",
                industry="Financial Services",
                size=10000,
                region="UAE",
                website="https://www.bankfab.com/",
                challenges=[
                    "Complaint SLA visibility across channels",
                    "Churn in youth/SME segments",
                    "Measuring NPS impact by product",
                ],
                tech_stack=["Oracle", "Snowflake", "Adobe Analytics"],
                last_enriched_at=now,
            ),
            Company(
                id="c3",
                name="Carrefour Saudi Arabia (Majid Al Futtaim)",
                domain="carrefourksa.com",
                industry="Retail (Grocery)",
                size=8000,
                region="KSA",
                website="https://www.carrefourksa.com/",
                challenges=[
                    "Store-level review consistency",
                    "Attribution of social buzz to sales",
                    "Arabic sentiment nuances for product categories",
                ],
                tech_stack=["SAP", "Segment", "Google Analytics"],
                last_enriched_at=now,
            ),
        ]
