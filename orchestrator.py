"""
CleanFlow Orchestrator — Coordina todos los agentes en un pipeline unificado.

Pipeline completo:
  1. Lead Scraper → busca oportunidades
  2. Lead Qualifier → califica con IA + scoring
  3. Subcontractor Matcher → empareja con subs
  4. Proposal Generator → genera bids
  5. Follow-up Agent → seguimiento automático
  6. Performance Monitor → monitorea contratos activos

Modos de ejecución:
  - full: ejecuta todo el pipeline (1→4)
  - scrape: solo scraping + calificación (1→2)
  - match: solo matching + propuestas (3→4)
  - followup: solo follow-ups (5)
  - monitor: solo monitoreo (6)
"""
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from agents.lead_scraper import LeadScraperAgent
from agents.lead_qualifier import LeadQualifierAgent
from agents.subcontractor_matcher import SubcontractorMatcherAgent
from agents.proposal_generator import ProposalGeneratorAgent
from agents.followup_agent import FollowUpAgent
from agents.performance_monitor import PerformanceMonitorAgent
from core.notifications import notifier

# ─── LOGGING ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("cleanflow.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("cleanflow.orchestrator")


class Orchestrator:
    """Coordina la ejecución de todos los agentes."""

    def __init__(self):
        self.scraper = LeadScraperAgent()
        self.qualifier = LeadQualifierAgent()
        self.matcher = SubcontractorMatcherAgent()
        self.proposal_gen = ProposalGeneratorAgent()
        self.followup = FollowUpAgent()
        self.monitor = PerformanceMonitorAgent()

    # ─── PIPELINE COMPLETO ─────────────────────────

    def run_full_pipeline(self, max_queries: Optional[int] = None) -> Dict[str, Any]:
        """Ejecuta el pipeline completo: scrape → qualify → match → propose."""
        logger.info("=" * 60)
        logger.info("🚀 PIPELINE COMPLETO INICIANDO")
        logger.info("=" * 60)
        start = datetime.now(timezone.utc)
        results = {}

        # Paso 1: Scraping
        logger.info("─── PASO 1/4: SCRAPING ───")
        scrape_result = self.scraper.safe_run(max_queries=max_queries)
        results["scraping"] = scrape_result
        leads = scrape_result.get("leads", [])

        if not leads:
            logger.info("Sin leads nuevos, terminando pipeline")
            results["status"] = "no_leads"
            return results

        # Paso 2: Calificación
        logger.info("─── PASO 2/4: CALIFICACIÓN ───")
        qualify_result = self.qualifier.safe_run(leads=leads)
        results["qualification"] = qualify_result
        qualified = qualify_result.get("qualified_leads", [])

        if not qualified:
            logger.info("Sin leads calificados, terminando pipeline")
            results["status"] = "no_qualified"
            return results

        # Paso 3: Matching
        logger.info("─── PASO 3/4: MATCHING ───")
        match_result = self.matcher.safe_run(opportunities=qualified)
        results["matching"] = match_result
        matches = match_result.get("matches", [])

        if not matches:
            logger.info("Sin matches, terminando pipeline")
            results["status"] = "no_matches"
            return results

        # Paso 4: Propuestas
        logger.info("─── PASO 4/4: PROPUESTAS ───")
        proposal_result = self.proposal_gen.safe_run(matches=matches)
        results["proposals"] = proposal_result

        # Resumen
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["status"] = "completed"
        results["total_elapsed_seconds"] = elapsed

        summary = (
            f"✅ *PIPELINE COMPLETADO*\n\n"
            f"⏱ Tiempo: {elapsed:.0f}s\n"
            f"🔍 Leads scrapeados: {scrape_result.get('total_unique', 0)}\n"
            f"✅ Calificados: {qualify_result.get('qualified', 0)}\n"
            f"🔥 Hot leads: {qualify_result.get('hot_leads', 0)}\n"
            f"🤝 Matched: {match_result.get('matched', 0)}\n"
            f"📝 Bids creadas: {proposal_result.get('bids_created', 0)}"
        )
        notifier.send_telegram(summary)
        logger.info(summary.replace("*", ""))

        return results

    # ─── MODOS INDIVIDUALES ────────────────────────

    def run_scrape_only(self, max_queries: Optional[int] = None) -> Dict:
        """Solo scraping + calificación."""
        scrape = self.scraper.safe_run(max_queries=max_queries)
        leads = scrape.get("leads", [])
        if leads:
            qualify = self.qualifier.safe_run(leads=leads)
            return {"scraping": scrape, "qualification": qualify}
        return {"scraping": scrape}

    def run_match_and_propose(self) -> Dict:
        """Match + propuestas para oportunidades ya calificadas."""
        match = self.matcher.safe_run()
        matches = match.get("matches", [])
        if matches:
            proposals = self.proposal_gen.safe_run(matches=matches)
            return {"matching": match, "proposals": proposals}
        return {"matching": match}

    def run_followups(self) -> Dict:
        """Solo follow-ups."""
        return self.followup.safe_run()

    def run_monitor(self, contracts=None) -> Dict:
        """Solo monitoreo de performance."""
        return self.monitor.safe_run(contracts=contracts)


# ─── CLI ───────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="CleanFlow Agent Orchestrator")
    parser.add_argument(
        "mode",
        choices=["full", "scrape", "match", "followup", "monitor"],
        default="full",
        nargs="?",
        help="Modo de ejecución",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Limitar número de queries de búsqueda (para testing)",
    )
    args = parser.parse_args()

    orchestrator = Orchestrator()

    if args.mode == "full":
        result = orchestrator.run_full_pipeline(max_queries=args.max_queries)
    elif args.mode == "scrape":
        result = orchestrator.run_scrape_only(max_queries=args.max_queries)
    elif args.mode == "match":
        result = orchestrator.run_match_and_propose()
    elif args.mode == "followup":
        result = orchestrator.run_followups()
    elif args.mode == "monitor":
        result = orchestrator.run_monitor()
    else:
        result = {"error": f"Modo desconocido: {args.mode}"}

    logger.info(f"Resultado final: {result.get('status', 'unknown')}")


if __name__ == "__main__":
    main()
