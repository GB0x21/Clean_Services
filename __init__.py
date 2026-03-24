"""
CleanFlow Agents — Sistema de automatización para servicios de limpieza comercial.

Agentes:
  1. LeadScraperAgent      — Búsqueda de oportunidades
  2. LeadQualifierAgent    — Calificación con IA + scoring
  3. SubcontractorMatcher  — Match con subcontratistas
  4. ProposalGenerator     — Generación de propuestas
  5. FollowUpAgent         — Seguimiento automático
  6. PerformanceMonitor    — Monitoreo de contratos

Uso:
  python orchestrator.py full         # Pipeline completo
  python orchestrator.py scrape       # Solo scraping
  python orchestrator.py match        # Solo matching
  python orchestrator.py followup     # Solo follow-ups
  python orchestrator.py monitor      # Solo monitoreo
  python scheduler.py                 # Scheduler automático
"""
import os
from pathlib import Path

# Cargar .env si existe
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
