"""
Agent Registry — Sistema de registro, health check, y coordinación multi-agente.
Inspirado en el patrón Agents Orchestrator de agency-agents.

Funcionalidades:
  - Registro de agentes con metadata
  - Health tracking (último run, errores, stats)
  - Dependency graph (quién depende de quién)
  - Smart retry con backoff exponencial
  - Pipeline builder para encadenar agentes
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("cleanflow.registry")


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class AgentHealth:
    """Tracking de salud de un agente."""
    status: AgentStatus = AgentStatus.IDLE
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_errors: int = 0
    total_runs: int = 0
    total_errors: int = 0
    avg_runtime_seconds: float = 0.0
    last_result: Optional[Dict] = None


@dataclass
class AgentRegistration:
    """Registro de un agente en el sistema."""
    name: str
    agent_instance: Any  # BaseAgent
    description: str = ""
    division: str = "core"  # engineering, sales, operations, etc.
    dependencies: List[str] = field(default_factory=list)
    health: AgentHealth = field(default_factory=AgentHealth)
    max_retries: int = 3
    retry_backoff_seconds: float = 5.0
    enabled: bool = True


class AgentRegistry:
    """
    Registro central de todos los agentes.
    Permite coordinación, health checks, y ejecución con retry.
    """

    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}
        self._execution_history: List[Dict] = []

    # ─── REGISTRATION ──────────────────────────────

    def register(
        self,
        name: str,
        agent_instance: Any,
        description: str = "",
        division: str = "core",
        dependencies: Optional[List[str]] = None,
        max_retries: int = 3,
    ) -> None:
        """Registra un agente en el sistema."""
        reg = AgentRegistration(
            name=name,
            agent_instance=agent_instance,
            description=description,
            division=division,
            dependencies=dependencies or [],
            max_retries=max_retries,
        )
        self._agents[name] = reg
        logger.info(f"Registered agent: {name} ({division})")

    def get(self, name: str) -> Optional[AgentRegistration]:
        return self._agents.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": reg.name,
                "division": reg.division,
                "status": reg.health.status.value,
                "enabled": reg.enabled,
                "total_runs": reg.health.total_runs,
                "consecutive_errors": reg.health.consecutive_errors,
                "last_run": reg.health.last_run_at.isoformat()
                if reg.health.last_run_at else None,
            }
            for reg in self._agents.values()
        ]

    # ─── HEALTH CHECKS ─────────────────────────────

    def is_healthy(self, name: str) -> bool:
        """Un agente es healthy si no tiene errores consecutivos excesivos."""
        reg = self.get(name)
        if not reg:
            return False
        if not reg.enabled:
            return False
        if reg.health.consecutive_errors >= reg.max_retries:
            return False
        return True

    def get_unhealthy_agents(self) -> List[str]:
        return [
            name for name, reg in self._agents.items()
            if not self.is_healthy(name)
        ]

    def reset_health(self, name: str) -> None:
        reg = self.get(name)
        if reg:
            reg.health.consecutive_errors = 0
            reg.health.status = AgentStatus.IDLE
            reg.health.last_error = None

    # ─── EXECUTION ─────────────────────────────────

    def execute(
        self,
        name: str,
        retry: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ejecuta un agente con health tracking y retry automático.
        Verifica dependencias antes de ejecutar.
        """
        reg = self.get(name)
        if not reg:
            return {"status": "error", "error": f"Agent '{name}' not registered"}

        if not reg.enabled:
            return {"status": "skipped", "reason": "agent disabled"}

        # Check dependencies
        for dep in reg.dependencies:
            if not self.is_healthy(dep):
                return {
                    "status": "error",
                    "error": f"Dependency '{dep}' is unhealthy",
                }

        # Execute with retry
        attempts = reg.max_retries if retry else 1
        last_error = None

        for attempt in range(1, attempts + 1):
            start = datetime.now(timezone.utc)
            reg.health.status = AgentStatus.RUNNING
            reg.health.last_run_at = start
            reg.health.total_runs += 1

            try:
                result = reg.agent_instance.run(**kwargs)
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()

                # Update health — success
                reg.health.status = AgentStatus.SUCCESS
                reg.health.last_success_at = datetime.now(timezone.utc)
                reg.health.consecutive_errors = 0
                reg.health.last_result = result
                reg.health.avg_runtime_seconds = (
                    (reg.health.avg_runtime_seconds * (reg.health.total_runs - 1) + elapsed)
                    / reg.health.total_runs
                )

                # Log execution
                self._execution_history.append({
                    "agent": name,
                    "attempt": attempt,
                    "status": "success",
                    "elapsed": elapsed,
                    "timestamp": start.isoformat(),
                })

                result["_meta"] = {
                    "agent": name,
                    "attempt": attempt,
                    "elapsed": elapsed,
                }
                return result

            except Exception as e:
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                last_error = str(e)
                reg.health.consecutive_errors += 1
                reg.health.total_errors += 1
                reg.health.last_error = last_error
                reg.health.status = AgentStatus.ERROR

                self._execution_history.append({
                    "agent": name,
                    "attempt": attempt,
                    "status": "error",
                    "error": last_error,
                    "elapsed": elapsed,
                    "timestamp": start.isoformat(),
                })

                logger.warning(
                    f"Agent '{name}' attempt {attempt}/{attempts} failed: {e}"
                )

                if attempt < attempts:
                    backoff = reg.retry_backoff_seconds * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {backoff}s...")
                    time.sleep(backoff)

        return {
            "status": "error",
            "error": last_error,
            "attempts": attempts,
        }

    # ─── PIPELINE ──────────────────────────────────

    def execute_pipeline(
        self,
        steps: List[Tuple[str, Dict[str, Any]]],
        stop_on_error: bool = True,
    ) -> Dict[str, Any]:
        """
        Ejecuta una secuencia de agentes, pasando outputs como inputs.
        
        steps = [
            ("lead_scraper", {"max_queries": 5}),
            ("lead_qualifier", {}),  # recibe output del paso anterior
            ("subcontractor_matcher", {}),
            ("proposal_generator", {}),
        ]
        """
        results = {}
        previous_output = {}

        for agent_name, extra_kwargs in steps:
            # Merge previous output como input del siguiente
            kwargs = {**extra_kwargs}
            if previous_output:
                kwargs["_previous"] = previous_output

            result = self.execute(agent_name, **kwargs)
            results[agent_name] = result

            if result.get("status") == "error" and stop_on_error:
                logger.error(
                    f"Pipeline stopped at '{agent_name}': {result.get('error')}"
                )
                results["_pipeline_status"] = "stopped"
                results["_stopped_at"] = agent_name
                return results

            previous_output = result

        results["_pipeline_status"] = "completed"
        return results

    # ─── REPORTING ─────────────────────────────────

    def get_dashboard(self) -> Dict[str, Any]:
        """Genera un dashboard del estado de todos los agentes."""
        agents = self.list_agents()
        return {
            "total_agents": len(agents),
            "healthy": sum(1 for a in agents if self.is_healthy(a["name"])),
            "unhealthy": self.get_unhealthy_agents(),
            "agents": agents,
            "recent_executions": self._execution_history[-20:],
        }


# Singleton
registry = AgentRegistry()
