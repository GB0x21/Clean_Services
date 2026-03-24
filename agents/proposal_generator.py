"""
Proposal Generator Agent — Genera propuestas profesionales con IA.
Crea bids listos para revisión y envío.
"""
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from config.settings import config

logger = logging.getLogger("cleanflow.proposal")

PROPOSAL_SYSTEM_PROMPT = """You are an expert business proposal writer for a commercial
cleaning and facility maintenance company. Write professional, compelling proposals that
win contracts.

Style guidelines:
- Professional but warm tone
- Solution-oriented, not salesy
- Highlight reliability, quality, and flexibility
- Include specific details about approach and methodology
- Strong call-to-action
- Written in English
"""

PROPOSAL_USER_PROMPT = """Create a professional service proposal for this opportunity:

CLIENT INFORMATION:
- Client: {client_name}
- Location: {city}, {state}
- Type: {client_type}
- Services Needed: {service_types}
- Description: {description}

OUR PROPOSAL:
- Proposed Price: ${bid_amount:,.2f}
- Payment Terms: Net {payment_terms}
- Estimated Start: Within 5 business days of acceptance
- Subcontractor: {sub_name} (Quality Score: {sub_quality}/5)

Write a 300-400 word proposal that includes:
1. Professional greeting addressing the client by name
2. Understanding of their specific cleaning/maintenance needs
3. Our approach: we deploy verified, insured local professionals
4. Service schedule and methodology
5. Clear pricing and payment terms
6. Why we're the best choice (quality guarantee, reliability, flexibility)
7. Strong call-to-action with next steps

Do NOT include any JSON. Write the proposal as clean professional text.
"""

EMAIL_SUBJECT_PROMPT = """Generate a professional email subject line for a commercial
cleaning services proposal to {client_name} in {city}, {state}.
Return ONLY the subject line, nothing else. Max 60 characters."""


class ProposalGeneratorAgent(BaseAgent):
    """
    Toma matches (oportunidad + subcontratista) y genera:
    1. Propuesta profesional en texto
    2. Subject line para email
    3. Registro de bid en Supabase
    """

    def __init__(self):
        super().__init__("proposal_generator")

    # ─── GENERATE PROPOSAL TEXT ────────────────────

    def _generate_proposal(
        self, opportunity: Dict, match: Dict
    ) -> str:
        """Genera el texto de la propuesta con IA."""
        prompt = PROPOSAL_USER_PROMPT.format(
            client_name=opportunity.get("client_name", "Valued Client"),
            city=opportunity.get("city", ""),
            state=opportunity.get("state", ""),
            client_type=opportunity.get("client_type", "commercial"),
            service_types=", ".join(opportunity.get("service_types", ["cleaning"])),
            description=opportunity.get("description", "Commercial cleaning services"),
            bid_amount=match.get("bid_amount", 0),
            payment_terms=opportunity.get("payment_terms_days", 30),
            sub_name=match.get("subcontractor_name", "our local team"),
            sub_quality=match.get("quality_score", 4),
        )
        return self.ai.ask(
            PROPOSAL_SYSTEM_PROMPT, prompt, temperature=0.7, max_tokens=1500
        )

    def _generate_subject(self, opportunity: Dict) -> str:
        """Genera subject line para el email."""
        prompt = EMAIL_SUBJECT_PROMPT.format(
            client_name=opportunity.get("client_name", "your company"),
            city=opportunity.get("city", ""),
            state=opportunity.get("state", ""),
        )
        return self.ai.ask(
            "You generate email subject lines.", prompt, temperature=0.5, max_tokens=50
        ).strip('"').strip("'")

    # ─── CREATE BID ────────────────────────────────

    def _create_bid(
        self, opportunity: Dict, match: Dict, proposal_text: str, subject: str
    ) -> Dict:
        """Guarda el bid en Supabase."""
        bid_data = {
            "opportunity_id": opportunity.get("id"),
            "bid_amount": match.get("bid_amount", 0),
            "estimated_cost": match.get("estimated_cost", 0),
            "estimated_margin": match.get("estimated_margin_pct", 0),
            "estimated_profit": match.get("estimated_profit", 0),
            "subcontractor_id": match.get("subcontractor_id"),
            "subcontractor_name": match.get("subcontractor_name"),
            "proposal_text": proposal_text,
            "email_subject": subject,
            "match_score": match.get("match_score", 0),
            "cashflow_advantage_days": match.get("cashflow_advantage_days", 0),
            "status": "draft",
            "generated_by_ai": True,
        }
        return self.db.insert_bid(bid_data)

    # ─── RUN PRINCIPAL ─────────────────────────────

    def run(
        self,
        matches: Optional[List[Dict]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Espera una lista de dicts con formato:
        [{"opportunity": {...}, "best_match": {...}}, ...]
        """
        if not matches:
            return {"total": 0, "bids_created": 0, "bids": []}

        bids_created = []
        errors = []

        for match_result in matches:
            opp = match_result["opportunity"]
            best = match_result["best_match"]

            try:
                # Generar propuesta
                proposal_text = self._generate_proposal(opp, best)
                subject = self._generate_subject(opp)

                # Guardar bid
                bid = self._create_bid(opp, best, proposal_text, subject)
                bids_created.append({
                    "bid": bid,
                    "opportunity_title": opp.get("title"),
                    "bid_amount": best.get("bid_amount"),
                    "margin": best.get("estimated_margin_pct"),
                })

                # Actualizar status de oportunidad
                self.db.update_opportunity(
                    opp["id"], {"status": "bid_created"}
                )

                # Notificar bid lista
                self.notifier.alert_bid_ready(bid, opp)

                logger.info(
                    f"Bid creada: {opp.get('title', '')[:40]} "
                    f"→ ${best.get('bid_amount', 0):,.0f}"
                )

            except Exception as e:
                logger.error(f"Error generando propuesta: {e}")
                errors.append({"opportunity": opp.get("title"), "error": str(e)})

        return {
            "total": len(matches),
            "bids_created": len(bids_created),
            "errors": len(errors),
            "bids": bids_created,
        }
