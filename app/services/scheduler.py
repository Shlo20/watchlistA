"""APScheduler integration — daily digest and auto-archive on a cron schedule."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="America/New_York")


def _run_digest() -> None:
    from app.services.notifications import send_daily_digest
    logger.info("Daily digest firing...")
    count = send_daily_digest()
    logger.info("Daily digest fired — %d items sent to buyers", count)


def _run_archive() -> None:
    from app.services.archive import archive_stale_pending_requests
    logger.info("Auto-archive firing...")
    db = SessionLocal()
    try:
        count = archive_stale_pending_requests(db)
        logger.info("Auto-archive fired — archived %d requests", count)
    finally:
        db.close()


def start_scheduler() -> None:
    scheduler.add_job(
        _run_digest,
        CronTrigger(hour=settings.digest_hour, minute=0),
        id="daily_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_archive,
        CronTrigger(hour=settings.archive_hour, minute=0),
        id="archive_stale",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — digest at %02d:00, archive at %02d:00",
        settings.digest_hour,
        settings.archive_hour,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
