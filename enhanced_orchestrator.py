"""
CleanFlow Enhanced Orchestrator — Versión mejorada con:
  - Agent Registry para health tracking y retry automático
  - Agent Personalities para system prompts especializados
  - Pipeline builder para flujos configurables
  - Dashboard de estado
  - Modos de ejecución flexibles

Uso:
  python enhanced_orchestrator.py full         # Pipeline completo
  python enhanced_orchestrator.py scrape       # Solo scraping
  python enhanced_orchestrator.py match        # Solo matching
  python enhanced_orchestrator.py followup     # Solo follow-ups
  python enhanced_orchestrator.py monitor      # Solo monitoreo
  python enhanced_orchestrator.py dashboard    # Ver estado de agentes
  python enhanced_orchestrator.py full --max-queries 5 --dry-run
"""
import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Cargar .env
from pathlib import Path
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

from agents.lead_scraper import LeadScraperAgent
from agents.lead_qualifier import LeadQualifierAgent
from agents.subcontractor_matcher import SubcontractorMatcherAgent
from agents.proposal_generator import ProposalGeneratorAgent
from agents.followup_agent import FollowUpAgent
from agents.performance_monitor import PerformanceMonitorAgent
from core.agent_registry import registry, AgentRegistry
from core.notifications import notifier
from config.personalities import AGENT_PERSONALITIES, ORCHESTRATOR_PERSONALITY

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
logger = logging.getLogger("cleanflow.orchestrator.v2")


class EnhancedOrchestrator:
    """
    Orquestador mejorado con:
    - Registry: health tracking, retry, dependency checking
    - Personalities: cada agente tiene system prompt especializado
    - Pipeline: ejecución encadenada con data passing
    """

    def __init__(self):
        # Crear instancias de agentes
        self._scraper = LeadScraperAgent()
        self._qualifier = LeadQualifierAgent()
        self._matcher = SubcontractorMatcherAgent()
        self._proposal = ProposalGeneratorAgent()
        self._followup = FollowUpAgent()
        self._monitor = PerformanceMonitorAgent()

        # Registrar en el registry con metadata
        registry.register(
            "lead_scraper",
            self._scraper,
            description="Busca oportunidades en Google CSE y otras fuentes",
            division="prospecting",
            max_retries=2,
        )
        registry.register(
            "lead_qualifier",
            self._qualifier,
            description="Califica leads con IA + fórmula de scoring",
            division="sales",
            dependencies=["lead_scraper"],
            max_retries=2,
        )
        registry.register(
            "subcontractor_matcher",
            self._matcher,
            description="Empareja oportunidades con subcontratistas",
            division="operations",
            dependencies=["lead_qualifier"],
            max_retries=3,
        )
        registry.register(
            "proposal_generator",
            self._proposal,
            description="Genera propuestas profesionales con IA",
            division="sales",
            dependencies=["subcontractor_matcher"],
            max_retries=2,
        )
        registry.register(
            "followup",
            self._followup,
            description="Seguimiento automático de bids enviadas",
            division="sales",
            max_retries=1,
        )
        registry.register(
            "performance_monitor",
            self._monitor,
            description="Monitorea calidad de contratos activos",
            division="operations",
            max_retries=1,
        )

        logger.info(
            f"Enhanced Orchestrator initialized with "
            f"{len(registry.list_agents())} agents"
        )

    # ─── SMART PIPELINE ────────────────────────────

    def run_full_pipeline(
        self,
        max_queries: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Pipeline completo con health checks y data passing."""
        logger.info("=" * 60)
        logger.info("🚀 ENHANCED PIPELINE v2 INICIANDO")
        logger.info("=" * 60)
        start = datetime.now(timezone.utc)

        # Pre-flight: check all agents healthy
        unhealthy = registry.get_unhealthy_agents()
        if unhealthy:
            logger.warning(f"Unhealthy agents detected: {unhealthy}")
            # Reset si tienen menos de max_retries errores
            for name in unhealthy:
                reg = registry.get(name)
                if reg and reg.health.consecutive_errors < reg.max_retries:
                    registry.reset_health(name)

        results = {}

        # ── STEP 1: Scraping ──
        logger.info("─── STEP 1/4: PROSPECTING (Scout) ───")
        scrape_result = registry.execute(
            "lead_scraper", max_queries=max_queries
        )
        results["scraping"] = scrape_result
        leads = scrape_result.get("leads", [])

        if not leads:
            logger.info("Scout reports: no new leads found")
            self._send_summary(results, start, "no_leads")
            return results

        # ── STEP 2: Qualification ──
        logger.info("─── STEP 2/4: QUALIFICATION (Vetter) ───")
        qualify_result = registry.execute("lead_qualifier", leads=leads)
        results["qualification"] = qualify_result
        qualified = qualify_result.get("qualified_leads", [])

        if not qualified:
            logger.info("Vetter reports: no leads met qualification criteria")
            self._send_summary(results, start, "no_qualified")
            return results

        if dry_run:
            logger.info("DRY RUN — stopping after qualification")
            self._send_summary(results, start, "dry_run")
            return results

        # ── STEP 3: Matching ──
        logger.info("─── STEP 3/4: MATCHING (Bridge) ───")
        match_result = registry.execute(
            "subcontractor_matcher", opportunities=qualified
        )
        results["matching"] = match_result
        matches = match_result.get("matches", [])

        if not matches:
            logger.info("Bridge reports: no subcontractor matches found")
            # Alerta de escasez de subs
            if len(qualified) > 5:
                notifier.send_telegram(
                    "⚠️ *SUBCONTRACTOR SHORTAGE*\n"
                    f"{len(qualified)} qualified leads but 0 matches.\n"
                    "Action: recruit subcontractors in target cities."
                )
            self._send_summary(results, start, "no_matches")
            return results

        # ── STEP 4: Proposals ──
        logger.info("─── STEP 4/4: PROPOSALS (Quill) ───")
        proposal_result = registry.execute("proposal_generator", matches=matches)
        results["proposals"] = proposal_result

        self._send_summary(results, start, "completed")
        return results

    # ─── INDIVIDUAL MODES ──────────────────────────

    def run_scrape_only(self, max_queries: Optional[int] = None) -> Dict:
        scrape = registry.execute("lead_scraper", max_queries=max_queries)
        leads = scrape.get("leads", [])
        if leads:
            qualify = registry.execute("lead_qualifier", leads=leads)
            return {"scraping": scrape, "qualification": qualify}
        return {"scraping": scrape}

    def run_match_and_propose(self) -> Dict:
        match = registry.execute("subcontractor_matcher")
        matches = match.get("matches", [])
        if matches:
            proposals = registry.execute("proposal_generator", matches=matches)
            return {"matching": match, "proposals": proposals}
        return {"matching": match}

    def run_followups(self) -> Dict:
        return registry.execute("followup")

    def run_monitor(self, contracts=None) -> Dict:
        return registry.execute("performance_monitor", contracts=contracts)

    def get_dashboard(self) -> Dict:
        return registry.get_dashboard()

    # ─── SUMMARY ───────────────────────────────────

    def _send_summary(
        self, results: Dict, start: datetime, status: str
    ) -> None:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["status"] = status
        results["total_elapsed_seconds"] = elapsed

        scrape = results.get("scraping", {})
        qualify = results.get("qualification", {})
        match = results.get("matching", {})
        proposal = results.get("proposals", {})

        # Agent health summary
        dashboard = registry.get_dashboard()
        health_line = (
            f"🏥 Agents: {dashboard['healthy']}/{dashboard['total_agents']} healthy"
        )
        if dashboard["unhealthy"]:
            health_line += f" ⚠️ {', '.join(dashboard['unhealthy'])}"

        summary = (
            f"{'✅' if status == 'completed' else '⚡'} "
            f"*PIPELINE {'COMPLETED' if status == 'completed' else status.upper()}*\n\n"
            f"⏱ {elapsed:.0f}s\n"
            f"🔍 Scraped: {scrape.get('total_unique', 0)}\n"
            f"✅ Qualified: {qualify.get('qualified', 0)}\n"
            f"🔥 Hot: {qualify.get('hot_leads', 0)}\n"
            f"🤝 Matched: {match.get('matched', 0)}\n"
            f"📝 Bids: {proposal.get('bids_created', 0)}\n"
            f"{health_line}"
        )
        notifier.send_telegram(summary)
        logger.info(summary.replace("*", "").replace("\n", " | "))


# ─── CLI ───────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="CleanFlow Enhanced Orchestrator v2"
    )
    parser.add_argument(
        "mode",
        choices=["full", "scrape", "match", "followup", "monitor", "dashboard"],
        default="full",
        nargs="?",
    )
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo scrape + qualify, no matching ni propuestas",
    )
    args = parser.parse_args()

    orch = EnhancedOrchestrator()

    if args.mode == "full":
        orch.run_full_pipeline(
            max_queries=args.max_queries, dry_run=args.dry_run
        )
    elif args.mode == "scrape":
        orch.run_scrape_only(max_queries=args.max_queries)
    elif args.mode == "match":
        orch.run_match_and_propose()
    elif args.mode == "followup":
        orch.run_followups()
    elif args.mode == "monitor":
        orch.run_monitor()
    elif args.mode == "dashboard":
        dashboard = orch.get_dashboard()
        print(json.dumps(dashboard, indent=2, default=str))


if __name__ == "__main__":
    main()
