import os
import time
from seleniumbase import SB


# This locks the path to the 'scrapers/' folder where this script lives
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(SCRIPT_DIR, "stealth_profile")

MARKETPLACE_URL = "https://www.facebook.com/marketplace/glasgow/search?daysSinceListed=2&query=Vehicles&category_id=546583916084032&exact=false&referral_ui_component=category_menu_item&locale=en_GB"

def run():
    print(f"Loading profile from: {PROFILE_DIR}")
    
    with SB(uc=True, user_data_dir=PROFILE_DIR, headed=True) as sb:
        print("Navigating to Facebook Marketplace...")
        sb.driver.default_get(MARKETPLACE_URL) 
        
        time.sleep(4) 
        
        if "login" in sb.get_current_url() or sb.is_element_visible('input[type="password"]'):
            print("\n👉 ACTION REQUIRED: Logging in fresh for the scrapers/ folder location.")
            print("Please log in manually and click 'Save Browser' if prompted.")
            print("Press ENTER here when done...")
            input() 
            print("Saving session to disk...")
            time.sleep(5) 
        else:
            print("\n✅ Saved session loaded successfully from scrapers/stealth_profile!")
        
        print("✅ Ready to scrape!")
        time.sleep(5)

if __name__ == "__main__":
    run()