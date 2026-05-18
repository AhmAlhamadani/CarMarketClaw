from fastapi import APIRouter

from scrapers.fb_scraper import run as run_fb_scraper

router = APIRouter()


@router.post("/run")
def run_scraper():
    """Run the Facebook Marketplace scraper to completion (blocking)."""
    return run_fb_scraper(interactive_login=False)
