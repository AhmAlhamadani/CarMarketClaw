import logging
import threading

from scrapers.fb_scraper import run as run_fb_scraper

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def execute_fb_scrape(*, interactive_login: bool = False) -> dict | None:
    """
    Run the Facebook scraper. Returns None if another run is already in progress.
    """
    if not _lock.acquire(blocking=False):
        logger.warning("Facebook scrape skipped: a run is already in progress")
        return None
    try:
        logger.info("Facebook scrape starting (interactive_login=%s)", interactive_login)
        result = run_fb_scraper(interactive_login=interactive_login)
        logger.info("Facebook scrape finished")
        return result
    except Exception:
        logger.exception("Facebook scrape failed")
        raise
    finally:
        _lock.release()
