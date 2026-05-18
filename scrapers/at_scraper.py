from seleniumbase import SB
from at_filter_selection_scraper import run_interactive_scraper
from at_top_scraper import scrape_top_cars

URL = "https://www.autotrader.co.uk/car-search?postcode=G331RB&radius=100&sort=price-asc"

def run_pipeline():
    # 1. Open the browser ONCE here
    with SB(uc=True, test=False) as sb:
        print("Launching AutoTrader Pipeline...")
        sb.open(URL)
        sb.maximize_window()
        
        # 2. Pass the browser 'sb' to the filter script
        filter_data = run_interactive_scraper(sb)
        
        # 3. If filters were successful, pass the same browser to the extractor script
        if filter_data["success"]:
            car_results = scrape_top_cars(sb)
            
            # 4. Combine everything
            final_payload = {
                "filters_used": filter_data["filters"],
                "scraped_cars": car_results
            }
            
            print("\n" + "=" * 60)
            print("FINAL PIPELINE OUTPUT")
            print("=" * 60)
            import json
            print(json.dumps(final_payload, indent=2, ensure_ascii=False))
            
            input("\nPress Enter to close everything...")
            return final_payload

if __name__ == "__main__":
    run_pipeline()