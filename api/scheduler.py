import logging
import os
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from api.services.scraper_job import execute_fb_scrape

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _schedule_timezone() -> ZoneInfo | None:
    tz_name = os.getenv("SCRAPE_SCHEDULE_TZ", "").strip()
    if not tz_name:
        return None
    return ZoneInfo(tz_name)


def _run_scheduled_scrape() -> None:
    execute_fb_scrape(interactive_login=False)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    tz = _schedule_timezone()
    trigger = CronTrigger(hour="11,19", minute=0, timezone=tz)

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_scheduled_scrape,
        trigger,
        id="fb_scrape_daily",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()

    tz_label = tz.key if tz else "local system time"
    logger.info("Facebook scraper scheduled daily at 11:00 and 19:00 (%s)", tz_label)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    logger.info("Facebook scraper scheduler stopped")
