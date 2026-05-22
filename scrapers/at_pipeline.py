from collections.abc import Callable

from seleniumbase import SB

from scrapers.at_filter_selection_scraper import PromptFn, run_interactive_scraper
from scrapers.at_top_scraper import scrape_top_cars

URL = "https://www.autotrader.co.uk/car-search?postcode=G331RB&radius=100&sort=price-asc"


def fb_vehicle_suggestions(fb_vehicle: dict | None) -> dict:
    """Map fb_vehicles row fields to AutoTrader filter hints for the conversation."""
    if not fb_vehicle:
        return {}

    suggestions = {}
    if fb_vehicle.get("make"):
        suggestions["make"] = str(fb_vehicle["make"]).strip()
    if fb_vehicle.get("model"):
        suggestions["model"] = str(fb_vehicle["model"]).strip()

    transmission = fb_vehicle.get("transmission")
    if transmission == "automatic":
        suggestions["gearbox"] = "Automatic"
    elif transmission == "manual":
        suggestions["gearbox"] = "Manual"

    year = fb_vehicle.get("year")
    if year:
        suggestions["min_year"] = str(int(year))
        suggestions["max_year"] = str(int(year))

    mileage = fb_vehicle.get("mileage")
    if mileage:
        mileage = int(mileage)
        low = max(0, int(mileage * 0.8))
        high = int(mileage * 1.2)
        suggestions["min_mileage"] = f"{low:,}"
        suggestions["max_mileage"] = f"{high:,}"

    return suggestions


StatusFn = Callable[[str], None] | None


def run_pipeline(
    prompt_fn: PromptFn | None = None,
    fb_vehicle: dict | None = None,
    status_fn: StatusFn = None,
) -> dict:
    suggestions = fb_vehicle_suggestions(fb_vehicle)

    def status(msg: str) -> None:
        print(msg)
        if status_fn:
            status_fn(msg)

    status("Launching Chrome and opening AutoTrader (30–60 seconds)...")

    with SB(uc=True, test=False) as sb:
        sb.open(URL)
        sb.maximize_window()
        status("Browser ready. Opening filters — answer each question when it appears.")

        filter_data = run_interactive_scraper(sb, prompt_fn=prompt_fn, suggestions=suggestions)

        if not filter_data["success"]:
            return {
                "success": False,
                "filters_used": filter_data.get("filters", {}),
                "scraped_cars": [],
            }

        if filter_data.get("filters_stopped_early"):
            count = filter_data.get("search_result_count")
            status(
                f"Stopped adding filters early ({count} cars in preview, below 15)."
            )

        status("Search applied. Scraping top 3 listings (keep this window open)...")
        car_results = scrape_top_cars(sb)
        status(f"Scraped {len(car_results)} listing(s). Saving to database next...")
        return {
            "success": True,
            "filters_used": filter_data["filters"],
            "filters_stopped_early": filter_data.get("filters_stopped_early", False),
            "search_result_count": filter_data.get("search_result_count"),
            "scraped_cars": car_results,
        }
