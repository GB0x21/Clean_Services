"""
Base Agent — Clase abstracta para todos los agentes de CleanFlow.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.database import db
from core.ai_client import ai
from core.notifications import notifier


class BaseAgent(ABC):
    """Todos los agentes heredan de aquí."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"cleanflow.{name}")
        self.db = db
        self.ai = ai
        self.notifier = notifier
        self._run_stats: Dict[str, Any] = {}

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """Ejecutar la tarea principal del agente."""
        pass

    def safe_run(self, **kwargs) -> Dict[str, Any]:
        """Ejecuta run() con manejo de errores y logging."""
        start = datetime.now(timezone.utc)
        self.logger.info(f"▶ {self.name} iniciando...")
        try:
            result = self.run(**kwargs)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            self.logger.info(f"✅ {self.name} completado en {elapsed:.1f}s")
            result["elapsed_seconds"] = elapsed
            result["status"] = "success"
            return result
        except Exception as e:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            self.logger.error(f"❌ {self.name} falló: {e}", exc_info=True)
            self.notifier.alert_error(self.name, str(e))
            return {
                "status": "error",
                "error": str(e),
                "elapsed_seconds": elapsed,
            }
