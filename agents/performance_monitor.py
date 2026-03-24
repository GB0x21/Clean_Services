"""
Performance Monitor Agent — Monitorea contratos activos y calidad de subcontratistas.
Detecta riesgos y escala automáticamente.
"""
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger("cleanflow.performance")

RISK_SYSTEM_PROMPT = """You are a contract performance analyst for a commercial cleaning
company. Analyze contract performance data and assess risk levels.

Risk factors to consider:
- Subcontractor quality score trends
- Issue frequency
- Client communication sentiment
- Payment status
- Contract duration vs issues
"""

RISK_USER_PROMPT = """Analyze this contract performance:

Contract: {service_type} for {client_name}
Duration Active: {days_active} days
Subcontractor: {sub_name}, Quality Score: {quality_score}/5
Recent Issues: {issues_count} in last 30 days
Payment Status: {payment_status}
Contract Value: ${contract_value:,.0f}/month

Return ONLY this JSON:
{{
    "risk_level": "low" | "medium" | "high" | "critical",
    "risk_factors": ["factor1", "factor2"],
    "recommended_actions": ["action1", "action2"],
    "needs_immediate_attention": true/false,
    "predicted_satisfaction_score": 1-5,
    "notes": "brief analysis"
}}
"""


class PerformanceMonitorAgent(BaseAgent):
    """
    Revisa contratos activos, evalúa performance con IA,
    y escala según nivel de riesgo.
    """

    def __init__(self):
        super().__init__("performance_monitor")

    def _assess_risk(self, contract: Dict) -> Dict[str, Any]:
        """Evalúa riesgo de un contrato con IA."""
        prompt = RISK_USER_PROMPT.format(
            service_type=contract.get("service_type", "cleaning"),
            client_name=contract.get("client_name", "Unknown"),
            days_active=contract.get("days_active", 0),
            sub_name=contract.get("subcontractor_name", "Unknown"),
            quality_score=contract.get("quality_score", 3),
            issues_count=contract.get("issues_count", 0),
            payment_status=contract.get("payment_status", "on_time"),
            contract_value=contract.get("monthly_value", 0),
        )
        return self.ai.ask_json(RISK_SYSTEM_PROMPT, prompt)

    def _handle_critical(self, contract: Dict, assessment: Dict):
        """Escala contratos con riesgo crítico."""
        self.notifier.send_telegram(
            f"🚨 *RIESGO CRÍTICO*\n\n"
            f"Cliente: {contract.get('client_name')}\n"
            f"Contrato: ${contract.get('monthly_value', 0):,.0f}/mes\n"
            f"Sub: {contract.get('subcontractor_name')}\n\n"
            f"*Factores:*\n"
            + "\n".join(f"• {f}" for f in assessment.get("risk_factors", []))
            + "\n\n*Acciones recomendadas:*\n"
            + "\n".join(f"• {a}" for a in assessment.get("recommended_actions", []))
        )

    def run(self, contracts: Optional[List[Dict]] = None, **kwargs) -> Dict[str, Any]:
        if contracts is None:
            # En producción: obtener de Supabase tabla contract_performance
            contracts = []

        results = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        assessments = []

        for contract in contracts:
            assessment = self._assess_risk(contract)
            risk = assessment.get("risk_level", "low")
            results[risk] = results.get(risk, 0) + 1

            if risk == "critical":
                self._handle_critical(contract, assessment)
            elif risk == "high":
                self.notifier.send_telegram(
                    f"⚠️ Riesgo ALTO: {contract.get('client_name')} — "
                    f"Revisar pronto"
                )

            assessments.append({
                "contract": contract.get("client_name"),
                "risk_level": risk,
                "assessment": assessment,
            })

        return {
            "contracts_checked": len(contracts),
            "risk_summary": results,
            "assessments": assessments,
        }
