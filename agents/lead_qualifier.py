"""
Lead Qualifier Agent — Califica leads usando IA + reglas de negocio.
Aplica la fórmula de scoring definida en ContractCriteria.
Usa la personalidad "Vetter" de agency-agents.
"""
import logging
from typing import Any, Dict, List

from agents.base_agent import BaseAgent
from config.settings import config, SCORING_WEIGHTS
from config.personalities import get_personality

logger = logging.getLogger("cleanflow.qualifier")

QUALIFICATION_SYSTEM_PROMPT = get_personality("lead_qualifier") + """

Additionally, you are an expert commercial cleaning industry analyst.
Your job is to evaluate whether a lead/opportunity is a REAL commercial cleaning opportunity
worth pursuing for a cleaning services brokerage company.

The company operates in: AZ, TX, NV, FL
Preferred services: office cleaning, janitorial, post-construction cleaning, landscaping,
window cleaning (low-rise), parking lot maintenance, floor care.
Reject: hazmat, high-rise exterior, specialized medical, security clearance required.

Contract criteria:
- Minimum value: $3,000
- Ideal range: $8,000 - $40,000
- Max payment terms: Net 30 (reject Net 45+)
- Max licenses required: 2
"""

QUALIFICATION_USER_PROMPT = """Analyze this lead and return a JSON assessment:

Title: {title}
Description: {description}
Source URL: {source_url}
Source Platform: {source_platform}
City: {city}, State: {state}

Return ONLY this JSON structure:
{{
    "is_real_opportunity": true/false,
    "opportunity_type": "rfp" | "job_posting" | "vendor_request" | "procurement" | "bid_invitation" | "other",
    "client_type": "government" | "private" | "property_management" | "corporate" | "education" | "healthcare" | "retail" | "other",
    "client_name": "extracted client name or null",
    "service_types": ["cleaning", "janitorial", etc.],
    "estimated_value": number or null,
    "payment_terms_days": number or null,
    "is_recurring": true/false,
    "deadline": "date string or null",
    "contact_name": "name or null",
    "contact_email": "email or null",
    "contact_phone": "phone or null",
    "license_requirements": number (0-5),
    "urgency": "low" | "medium" | "high",
    "confidence_score": 0.0-1.0,
    "rejection_reason": "reason if not real opportunity, else null",
    "ai_notes": "brief analysis notes"
}}
"""


class LeadQualifierAgent(BaseAgent):
    """
    Toma leads crudos del scraper, los analiza con IA,
    aplica scoring de negocio, y los clasifica.
    """

    def __init__(self):
        super().__init__("lead_qualifier")

    # ─── AI ANALYSIS ───────────────────────────────

    def _analyze_lead(self, lead: Dict) -> Dict[str, Any]:
        """Usa OpenAI para analizar un lead individual."""
        prompt = QUALIFICATION_USER_PROMPT.format(
            title=lead.get("title", ""),
            description=lead.get("description", ""),
            source_url=lead.get("source_url", ""),
            source_platform=lead.get("source_platform", ""),
            city=lead.get("city", ""),
            state=lead.get("state", ""),
        )
        result = self.ai.ask_json(QUALIFICATION_SYSTEM_PROMPT, prompt)
        if "error" in result:
            logger.warning(f"AI analysis failed for: {lead.get('title')}")
            return {"is_real_opportunity": False, "rejection_reason": "ai_error"}
        return result

    # ─── BUSINESS SCORING ──────────────────────────

    def _calculate_score(self, lead: Dict, ai_analysis: Dict) -> float:
        """Aplica la fórmula de scoring del negocio."""
        criteria = config.criteria
        weights = SCORING_WEIGHTS

        # Factor 1: Valor del contrato (0-1)
        value = ai_analysis.get("estimated_value") or 0
        if value <= 0:
            value_score = 0.3  # valor desconocido = neutral
        elif value < criteria.min_value:
            value_score = 0.1
        elif criteria.ideal_min <= value <= criteria.ideal_max:
            value_score = 1.0
        else:
            value_score = min(value / criteria.ideal_max, 1.0)

        # Factor 2: Velocidad de pago (0-1)
        payment_days = ai_analysis.get("payment_terms_days")
        if payment_days is None:
            payment_score = 0.5
        elif payment_days <= criteria.ideal_payment_days:
            payment_score = 1.0
        elif payment_days <= criteria.max_payment_days:
            payment_score = 0.7
        else:
            payment_score = 0.1

        # Factor 3: Bajos requisitos (0-1)
        licenses = ai_analysis.get("license_requirements", 0)
        if licenses <= 1:
            req_score = 1.0
        elif licenses <= criteria.max_licenses:
            req_score = 0.6
        else:
            req_score = 0.1

        # Factor 4: Recurrencia (0-1)
        recurring = ai_analysis.get("is_recurring", False)
        recurrence_score = 1.0 if recurring else 0.4

        # Factor 5: Proximidad (0-1)
        city = lead.get("city", "")
        if city in criteria.tier_1_cities:
            prox_score = 1.0
        elif city in criteria.tier_2_cities:
            prox_score = 0.7
        elif city in criteria.tier_3_cities:
            prox_score = 0.4
        else:
            prox_score = 0.2

        # Score final ponderado
        score = (
            value_score * weights["contract_value"]
            + payment_score * weights["payment_speed"]
            + req_score * weights["low_requirements"]
            + recurrence_score * weights["recurrence"]
            + prox_score * weights["proximity"]
        )
        return round(score * 100, 1)  # 0-100

    # ─── CLASSIFY ──────────────────────────────────

    def _classify(self, score: float) -> str:
        criteria = config.criteria
        if score >= criteria.auto_pursue_threshold * 100:
            return "hot"
        elif score >= criteria.review_threshold * 100:
            return "warm"
        else:
            return "cold"

    # ─── RUN PRINCIPAL ─────────────────────────────

    def run(self, leads: List[Dict], **kwargs) -> Dict[str, Any]:
        qualified = []
        rejected = []
        hot_leads = []

        for lead in leads:
            ai_analysis = self._analyze_lead(lead)

            # Rechazar si no es oportunidad real
            if not ai_analysis.get("is_real_opportunity", False):
                rejected.append({
                    **lead,
                    "rejection_reason": ai_analysis.get("rejection_reason", "not_real"),
                })
                continue

            # Rechazar si confidence bajo
            if ai_analysis.get("confidence_score", 0) < 0.6:
                rejected.append({**lead, "rejection_reason": "low_confidence"})
                continue

            # Rechazar servicios no deseados
            services = ai_analysis.get("service_types", [])
            if any(s in config.criteria.reject_services for s in services):
                rejected.append({**lead, "rejection_reason": "rejected_service"})
                continue

            # Calcular score
            score = self._calculate_score(lead, ai_analysis)
            classification = self._classify(score)

            # Construir oportunidad completa
            opportunity = {
                **lead,
                **{k: v for k, v in ai_analysis.items() if k != "error"},
                "quality_score": score,
                "classification": classification,
                "status": "qualified" if classification in ("hot", "warm") else "review",
            }

            # Guardar en Supabase
            saved = self.db.insert_opportunity(opportunity)
            opportunity["id"] = saved.get("id")
            qualified.append(opportunity)

            # Alertar si es hot lead
            if classification == "hot":
                hot_leads.append(opportunity)
                self.notifier.alert_hot_lead(opportunity)

            logger.info(
                f"[{classification.upper()}] {lead.get('title', '')[:50]} "
                f"→ Score: {score}"
            )

        return {
            "total_analyzed": len(leads),
            "qualified": len(qualified),
            "rejected": len(rejected),
            "hot_leads": len(hot_leads),
            "qualified_leads": qualified,
            "hot_lead_details": hot_leads,
        }
