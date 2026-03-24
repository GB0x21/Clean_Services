"""
CleanFlow Scheduler — Ejecuta los agentes automáticamente.
Usa APScheduler para programar las ejecuciones.

Schedule por defecto:
  - Pipeline completo: cada 6 horas (9am, 3pm, 9pm, 3am)
  - Follow-ups: cada 24 horas (10am)
  - Performance monitor: cada 12 horas
"""
import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cleanflow.scheduler")

orchestrator = Orchestrator()
scheduler = BlockingScheduler()


def job_full_pipeline():
    logger.info("⏰ Scheduled: Full Pipeline")
    orchestrator.run_full_pipeline()


def job_followups():
    logger.info("⏰ Scheduled: Follow-ups")
    orchestrator.run_followups()


def job_monitor():
    logger.info("⏰ Scheduled: Performance Monitor")
    orchestrator.run_monitor()


def shutdown(signum, frame):
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Pipeline completo cada 6 horas (business hours bias)
    scheduler.add_job(
        job_full_pipeline,
        CronTrigger(hour="3,9,15,21", minute=0),
        id="full_pipeline",
        name="Full Pipeline (cada 6h)",
        misfire_grace_time=3600,
    )

    # Follow-ups diarios a las 10am
    scheduler.add_job(
        job_followups,
        CronTrigger(hour=10, minute=0),
        id="followups",
        name="Follow-ups (diario 10am)",
        misfire_grace_time=3600,
    )

    # Monitor cada 12 horas
    scheduler.add_job(
        job_monitor,
        CronTrigger(hour="8,20", minute=30),
        id="monitor",
        name="Performance Monitor (cada 12h)",
        misfire_grace_time=3600,
    )

    logger.info("=" * 50)
    logger.info("🕐 CleanFlow Scheduler iniciado")
    logger.info("Jobs programados:")
    for job in scheduler.get_jobs():
        logger.info(f"  → {job.name}: {job.trigger}")
    logger.info("=" * 50)

    scheduler.start()


if __name__ == "__main__":
    main()
