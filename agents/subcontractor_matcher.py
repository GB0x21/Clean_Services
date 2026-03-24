"""
Subcontractor Matcher Agent — Empareja oportunidades con subcontratistas.
Calcula pricing, márgenes, y cashflow advantage.
"""
import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from config.settings import config

logger = logging.getLogger("cleanflow.matcher")


class SubcontractorMatcherAgent(BaseAgent):
    """
    Para cada oportunidad calificada:
    1. Busca subcontratistas disponibles en la ciudad
    2. Score de match por servicios, calidad, disponibilidad
    3. Calcula pricing y margen
    4. Retorna top matches
    """

    def __init__(self):
        super().__init__("subcontractor_matcher")

    # ─── MATCH SCORING ─────────────────────────────

    def _score_match(
        self, opportunity: Dict, subcontractor: Dict
    ) -> Dict[str, Any]:
        """Calcula qué tan bien un sub encaja con la oportunidad."""
        reasons = []
        score = 0.0

        # 1. Service match (40%)
        opp_services = set(opportunity.get("service_types", []))
        sub_services = set(subcontractor.get("services_offered", []))
        if opp_services and sub_services:
            overlap = opp_services & sub_services
            service_score = len(overlap) / max(len(opp_services), 1)
        else:
            service_score = 0.5  # desconocido
        score += service_score * 0.40
        if service_score >= 0.8:
            reasons.append("Excelente match de servicios")

        # 2. Quality score (25%)
        quality = subcontractor.get("quality_score", 3) / 5.0
        score += quality * 0.25
        if quality >= 0.8:
            reasons.append(f"Alta calidad ({subcontractor.get('quality_score')}/5)")

        # 3. Availability (15%)
        avail = subcontractor.get("availability_status", "available")
        avail_score = 1.0 if avail == "available" else 0.5 if avail == "limited" else 0.0
        score += avail_score * 0.15
        if avail == "available":
            reasons.append("Disponible inmediatamente")

        # 4. Capacity (10%)
        max_jobs = subcontractor.get("max_simultaneous_jobs", 5)
        current_jobs = subcontractor.get("current_jobs", 0)
        capacity_score = max(0, (max_jobs - current_jobs) / max(max_jobs, 1))
        score += capacity_score * 0.10
        if capacity_score >= 0.8:
            reasons.append("Amplia capacidad disponible")

        # 5. Payment terms alignment (10%)
        sub_terms = subcontractor.get("payment_terms_days", 30)
        opp_terms = opportunity.get("payment_terms_days", 30) or 30
        if sub_terms > opp_terms:
            terms_score = 1.0  # Cashflow positivo
            cashflow_days = sub_terms - opp_terms
            reasons.append(f"Cashflow advantage: {cashflow_days} días")
        else:
            terms_score = 0.5
            cashflow_days = 0
        score += terms_score * 0.10

        return {
            "subcontractor_id": subcontractor.get("id"),
            "subcontractor_name": subcontractor.get("company_name", "N/A"),
            "match_score": round(score, 3),
            "match_reasons": reasons,
            "cashflow_advantage_days": cashflow_days,
            "availability": avail,
            "quality_score": subcontractor.get("quality_score", 0),
        }

    # ─── PRICING ───────────────────────────────────

    def _calculate_pricing(
        self, opportunity: Dict, subcontractor: Dict, match: Dict
    ) -> Dict[str, Any]:
        """Calcula el precio del bid, costo, y margen."""
        opp_value = opportunity.get("estimated_value", 0) or 0

        # Obtener pricing del sub
        pricing_model = subcontractor.get("pricing_model", {})
        if isinstance(pricing_model, str):
            import json
            try:
                pricing_model = json.loads(pricing_model)
            except:
                pricing_model = {}

        # Calcular costo estimado
        min_job = subcontractor.get("minimum_job_size", 500)
        if opp_value > 0:
            # Sub cobra ~60-70% del valor del contrato
            sub_rate = pricing_model.get("rate", 0.65)
            estimated_cost = max(opp_value * sub_rate, min_job)
        else:
            estimated_cost = min_job

        # Nuestro bid: costo + margen (30-40%)
        margin_pct = 0.35  # 35% margen target
        bid_amount = estimated_cost / (1 - margin_pct)
        actual_margin = ((bid_amount - estimated_cost) / bid_amount) * 100

        return {
            "bid_amount": round(bid_amount, 2),
            "estimated_cost": round(estimated_cost, 2),
            "estimated_margin_pct": round(actual_margin, 1),
            "estimated_profit": round(bid_amount - estimated_cost, 2),
        }

    # ─── FIND MATCHES ─────────────────────────────

    def _find_matches(
        self, opportunity: Dict, top_n: int = 3
    ) -> List[Dict[str, Any]]:
        """Encuentra los mejores subcontratistas para una oportunidad."""
        city = opportunity.get("city", "")
        subs = self.db.get_subcontractors(city=city, active_only=True)

        if not subs:
            # Intentar sin filtro de ciudad (buscar cercanos)
            subs = self.db.get_subcontractors(active_only=True)
            logger.info(f"No subs en {city}, buscando en todas las ciudades")

        if not subs:
            return []

        matches = []
        for sub in subs:
            match = self._score_match(opportunity, sub)
            if match["match_score"] >= 0.4:  # Mínimo para considerar
                pricing = self._calculate_pricing(opportunity, sub, match)
                matches.append({**match, **pricing})

        # Ordenar por score descendente
        matches.sort(key=lambda x: x["match_score"], reverse=True)
        return matches[:top_n]

    # ─── RUN PRINCIPAL ─────────────────────────────

    def run(
        self,
        opportunities: Optional[List[Dict]] = None,
        min_score: float = 50,
        **kwargs,
    ) -> Dict[str, Any]:
        # Si no se pasan, obtener de DB
        if opportunities is None:
            opportunities = self.db.get_opportunities(
                status="qualified", min_score=min_score
            )

        results = []
        no_match = []

        for opp in opportunities:
            matches = self._find_matches(opp)

            if not matches:
                no_match.append(opp)
                self.db.update_opportunity(
                    opp["id"],
                    {
                        "status": "no_match",
                        "ai_notes": "No suitable subcontractor found",
                    },
                )
                logger.warning(f"Sin match: {opp.get('title', '')[:50]}")
                continue

            best = matches[0]
            result = {
                "opportunity": opp,
                "best_match": best,
                "all_matches": matches,
            }
            results.append(result)

            # Actualizar oportunidad con match info
            self.db.update_opportunity(
                opp["id"],
                {
                    "status": "matched",
                    "matched_subcontractor_id": best["subcontractor_id"],
                    "ai_notes": f"Best match: {best['subcontractor_name']} "
                                f"(score: {best['match_score']:.2f})",
                },
            )
            logger.info(
                f"Match: {opp.get('title', '')[:40]} → "
                f"{best['subcontractor_name']} ({best['match_score']:.2f})"
            )

        return {
            "total_processed": len(opportunities),
            "matched": len(results),
            "no_match": len(no_match),
            "matches": results,
        }
