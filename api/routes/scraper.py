from fastapi import APIRouter, HTTPException

from api.services.scraper_job import execute_fb_scrape

router = APIRouter()


@router.api_route("/run", methods=["GET", "POST"])
def run_scraper():
    """Run the Facebook Marketplace scraper to completion (blocking)."""
    result = execute_fb_scrape(interactive_login=False)
    if result is None:
        raise HTTPException(status_code=409, detail="Scraper already running")
    return result
