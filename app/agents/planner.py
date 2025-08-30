class PlannerAgent:
    def plan(self, objective: str) -> list[str]:
        return [
            "discover_companies",
            "research_company",
            "enrich_profile",
            "find_people",
            "write_summary_and_email",
            "compliance_gate",
            "send_and_handoff"
        ]
