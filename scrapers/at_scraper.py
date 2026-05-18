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

def click_make_and_model_tab(sb):
    try:
        make_model_button = 'button[data-testid="make_and_model-facet-group"]'
        sb.wait_for_element_visible(make_model_button, timeout=10)
        sb.js_click(make_model_button)
    except Exception as e:
        print(f"Failed to click Make and Model button: {e}")

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

def ask_for_make(sb):
    """Scrapes makes and asks the user to choose one conversationally."""
    make_dropdown = "select#make"
    make_map = build_dropdown_map(sb, make_dropdown)
    
    if not make_map:
        print("\n[Error] Failed to read any makes from the webpage dropdown.")
        return False, None

    print("\n" + "=" * 60)
    print("STEP 1: CHOOSE A MAKE")
    print("=" * 60)
    for i, make in enumerate(make_map.keys(), 1):
        print(f"{make:<20}", end="\n" if i % 4 == 0 else "")
    print("\n" + "-" * 60)
    
    while True:
        user_choice = input("\nWhat Make are you looking for? (or press Enter to exit): ").strip()
        if not user_choice:
            return False, None
        if user_choice in make_map:
            sb.select_option_by_text(make_dropdown, make_map[user_choice])
            return True, user_choice
        print("Selection not recognized. Please match the text exactly (Case Sensitive).")

def ask_for_model(sb, selected_make):
    """Scrapes models for the chosen make and asks the user to choose one conversationally."""
    model_dropdown = "select#model"
    model_map = build_dropdown_map(sb, model_dropdown)
    
    if not model_map:
        print(f"\n[Error] Failed to read any models for {selected_make}.")
        return False, None

    print("\n" + "=" * 60)
    print(f"STEP 2: CHOOSE A MODEL FOR {selected_make.upper()}")
    print("=" * 60)
    for i, model in enumerate(model_map.keys(), 1):
        print(f"{model:<25}", end="\n" if i % 3 == 0 else "")
    print("\n" + "-" * 60)
    
    while True:
        user_choice = input(f"\nWhat Model are you looking for? (or press Enter to exit): ").strip()
        if not user_choice:
            return False, None
        if user_choice in model_map:
            sb.select_option_by_text(model_dropdown, model_map[user_choice])
            return True, user_choice
        print("Selection not recognized. Match the text exactly (Case Sensitive).")

def ask_for_trim(sb, selected_model):
    """Scrapes trims (if any) and asks the user to choose one conversationally."""
    trim_dropdown = "select#aggregated_trim"
    trim_map = build_dropdown_map(sb, trim_dropdown, timeout=3)
    
    if not trim_map:
        print(f"\n--> No specific trims available for the {selected_model}. Skipping this step.")
        return True, None

    print("\n" + "=" * 60)
    print(f"STEP 3: CHOOSE A TRIM FOR {selected_model.upper()}")
    print("=" * 60)
    for i, trim in enumerate(trim_map.keys(), 1):
        print(f"{trim:<25}", end="\n" if i % 3 == 0 else "")
    print("\n" + "-" * 60)
    
    while True:
        user_choice = input("\nWhat Trim are you looking for? (Press Enter to leave blank/Any): ").strip()
        if not user_choice:
            print("--> Bypassing trim selection.")
            return True, None
        if user_choice in trim_map:
            sb.select_option_by_text(trim_dropdown, trim_map[user_choice])
            return True, user_choice
        print("Selection not recognized. Match the text exactly.")

def run_interactive_scraper():
    response = {
        "success": False,
        "final_make": None,
        "final_model": None,
        "final_trim": None,
        "message": "User aborted the process."
    }

    with SB(uc=True, test=False) as sb:
        print("Launching OpenClaw Interactive Scraper...")
        sb.open(URL)
        sb.maximize_window()
        
        reject_cookies(sb)
        sb.wait(1)
        open_filters(sb)
        sb.wait(1)
        click_make_and_model_tab(sb)
        sb.wait(1)

        # ---- STEP 1: CONVERSATIONAL MAKE ----
        make_ok, final_make = ask_for_make(sb)
        if not make_ok:
            return response
        sb.wait(1.5) # Allow cascade updates to complete

        # ---- STEP 2: CONVERSATIONAL MODEL ----
        model_ok, final_model = ask_for_model(sb, final_make)
        if not model_ok:
            return response
        sb.wait(1.5)

        # ---- STEP 3: CONVERSATIONAL TRIM ----
        trim_ok, final_trim = ask_for_trim(sb, final_model)
        if not trim_ok:
            return response

        print(f"\n✅ All selections complete!")
        print(f"Active Filters -> Make: {final_make} | Model: {final_model} | Trim: {final_trim if final_trim else 'Any'}")
        
        sb.wait(2) # Brief pause to observe the final state in the browser
        
        response["success"] = True
        response["final_make"] = final_make
        response["final_model"] = final_model
        response["final_trim"] = final_trim
        response["message"] = "Parameters interactively applied successfully."
        
        # You can add logic here to trigger the "Apply Filters" or "Show X Results" button
        
        input("\nPress Enter to close the browser session and exit OpenClaw...")
        return response

if __name__ == "__main__":
    result = run_interactive_scraper()
    
    # Final data payload returned to OpenClaw orchestrator if needed
    if not result["success"]:
        print(f"\n[OpenClaw Alert] {result['message']}")
    else:
        print("\n[OpenClaw Success] Returning final parameter payload to the database...")