import re
import time
from seleniumbase import SB

URL = "https://www.autotrader.co.uk/car-search?postcode=G331RB&radius=100&sort=price-asc"

def reject_cookies(sb):
    try:
        iframe_selector = "iframe[id^='sp_message_iframe']"
        sb.switch_to_frame(iframe_selector, timeout=10)
        reject_button = 'button[title="Reject All"]'
        sb.wait_for_element_visible(reject_button, timeout=10)
        sb.js_click(reject_button)
    except Exception:
        pass
    finally:
        sb.switch_to_default_content()

def open_filters(sb):
    try:
        filter_button = 'button[data-testid="search-filter-toggle"]'
        sb.wait_for_element_visible(filter_button, timeout=10)
        sb.js_click(filter_button)
    except Exception as e:
        print(f"Could not open filters: {e}")

def click_accordion(sb, testid_name):
    """Generic function to open any sidebar accordion tab based on its data-testid"""
    try:
        button_selector = f'button[data-testid="{testid_name}"]'
        sb.wait_for_element_visible(button_selector, timeout=10)
        sb.js_click(button_selector)
    except Exception as e:
        print(f"Failed to click accordion {testid_name}: {e}")

def build_dropdown_map(sb, selector, timeout=10):
    """Scrapes the targeted select element and builds a clean-to-raw dictionary mapping."""
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)
        raw_options = sb.get_select_options(selector)
        
        mapping = {}
        for opt in raw_options:
            if opt != "Any":
                clean_name = re.sub(r'\s*\([\d,]+\)', '', opt).strip()
                mapping[clean_name] = opt
        return mapping
    except Exception:
        return {}

def ask_for_single_choice(sb, dropdown_selector, step_title, prompt_text):
    """Handles standard single-choice dropdowns conversationally."""
    options_map = build_dropdown_map(sb, dropdown_selector, timeout=5)
    
    if not options_map:
        print(f"\n--> No options available for {step_title}. Skipping this step.")
        return True, None

    print("\n" + "=" * 60)
    print(f"{step_title.upper()}")
    print("=" * 60)
    for i, opt in enumerate(options_map.keys(), 1):
        print(f"{opt:<25}", end="\n" if i % 3 == 0 else "")
    print("\n" + "-" * 60)
    
    while True:
        user_choice = input(f"\n{prompt_text} (Press Enter to leave blank/Any): ").strip()
        if not user_choice:
            print(f"--> Bypassing {step_title} selection.")
            return True, None
        if user_choice in options_map:
            sb.select_option_by_text(dropdown_selector, options_map[user_choice])
            return True, user_choice
        print("Selection not recognized. Match the text exactly.")

def ask_for_range(sb, min_selector, max_selector, step_title):
    """
    Handles 'From' and 'To' dropdowns. Asks for Min, updates the page, 
    then asks for Max, dynamically reflecting restricted options.
    """
    print("\n" + "=" * 60)
    print(f"{step_title.upper()}")
    print("=" * 60)
    
    final_min = None
    final_max = None
    
    # 1. Handle MINIMUM (From)
    min_map = build_dropdown_map(sb, min_selector, timeout=5)
    if min_map:
        print(f"\n--- SELECT MINIMUM (FROM) ---")
        for i, opt in enumerate(min_map.keys(), 1):
            print(f"{opt:<20}", end="\n" if i % 4 == 0 else "")
        print("\n" + "-" * 60)
        
        while True:
            min_choice = input("Select 'From' value (Press Enter for Any): ").strip()
            if not min_choice:
                break
            if min_choice in min_map:
                sb.select_option_by_text(min_selector, min_map[min_choice])
                final_min = min_choice
                # Wait for the website to update the 'To' options based on this min choice
                sb.wait(1.5) 
                break
            print("Selection not recognized. Match the text exactly.")

    # 2. Handle MAXIMUM (To)
    max_map = build_dropdown_map(sb, max_selector, timeout=5)
    if max_map:
        print(f"\n--- SELECT MAXIMUM (TO) ---")
        for i, opt in enumerate(max_map.keys(), 1):
            print(f"{opt:<20}", end="\n" if i % 4 == 0 else "")
        print("\n" + "-" * 60)
        
        while True:
            max_choice = input("Select 'To' value (Press Enter for Any): ").strip()
            if not max_choice:
                break
            if max_choice in max_map:
                sb.select_option_by_text(max_selector, max_map[max_choice])
                final_max = max_choice
                break
            print("Selection not recognized. Match the text exactly.")

    return True, final_min, final_max

def run_interactive_scraper():
    response = {
        "success": False,
        "filters": {}
    }

    with SB(uc=True, test=False) as sb:
        print("Launching OpenClaw Interactive Scraper...")
        sb.open(URL)
        sb.maximize_window()
        
        reject_cookies(sb)
        sb.wait(1)
        open_filters(sb)
        sb.wait(1)

        # ---- STEP 1: MAKE & MODEL ----
        click_accordion(sb, "make_and_model-facet-group")
        sb.wait(1)
        
        _, final_make = ask_for_single_choice(sb, "select#make", "STEP 1: CHOOSE A MAKE", "What Make are you looking for?")
        if final_make:
            sb.wait(1.5)
            _, final_model = ask_for_single_choice(sb, "select#model", f"STEP 2: CHOOSE A MODEL FOR {final_make}", "What Model are you looking for?")
            if final_model:
                sb.wait(1.5)
                _, final_trim = ask_for_single_choice(sb, "select#aggregated_trim", f"STEP 3: CHOOSE A TRIM FOR {final_model}", "What Trim are you looking for?")
        
        # ---- STEP 4: MILEAGE RANGE ----
        # Using the HTML snippet you provided (min_mileage / max_mileage)
        # Note: If you want to do Year, change the selectors to select#year-from and select#year-to (or whatever AutoTrader uses)
        
        # Let's pretend the mileage dropdowns are inside a "Mileage" accordion 
        # (AutoTrader usually uses "mileage-facet-group")
        click_accordion(sb, "mileage-facet-group") 
        sb.wait(1)
        
        _, min_miles, max_miles = ask_for_range(sb, "select#min_mileage", "select#max_mileage", "STEP 4: SET MILEAGE RANGE")

        # ---- SUMMARY ----
        print(f"\n✅ All selections complete!")
        print(f"Make: {final_make} | Model: {final_model} | Trim: {final_trim if 'final_trim' in locals() and final_trim else 'Any'}")
        print(f"Mileage: {min_miles if min_miles else 'Any'} to {max_miles if max_miles else 'Any'}")
        
        response["success"] = True
        response["filters"] = {
            "make": final_make,
            "model": final_model,
            "min_mileage": min_miles,
            "max_mileage": max_miles
        }
        
        input("\nPress Enter to close the browser session and exit OpenClaw...")
        return response

if __name__ == "__main__":
    result = run_interactive_scraper()
    
    if result["success"]:
        print("\n[OpenClaw Success] Returning final parameter payload to the database...")