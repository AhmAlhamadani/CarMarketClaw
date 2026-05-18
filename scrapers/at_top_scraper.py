import re
from selenium.webdriver.common.by import By

def scrape_top_cars(sb):
    print("\n" + "=" * 60)
    print("STEP 8: SCRAPING TOP 3 NON-AD CARS")
    print("=" * 60)
    
    scraped_cars = []
    
    try:
        print("--> Waiting for search results to load...")
        sb.wait_for_element_visible('li[data-advertid]', timeout=15)
        sb.wait(2) 
    except Exception as e:
        print(f"--> Error waiting for results: {e}")
        return scraped_cars

    car_cards = sb.find_elements('li[data-advertid]')
    
    for card in car_cards:
        if len(scraped_cars) >= 3:
            break
            
        card_html = card.get_attribute('innerHTML')
        if 'data-testid="PROMOTED_LISTING"' in card_html or 'data-testid="GPT_LISTING"' in card_html:
            continue 

        try:
            title_el = card.find_element(By.CSS_SELECTOR, '[data-testid="search-listing-title"]')
            raw_title = title_el.text 
            
            try:
                trim = card.find_element(By.CSS_SELECTOR, '[data-testid="search-listing-subtitle"]').text
            except:
                trim = "N/A"

            try:
                mileage = card.find_element(By.CSS_SELECTOR, '[data-testid="mileage"]').text
            except:
                mileage = "N/A"
                
            # --- JUST THE YEAR ---
            try:
                raw_year = card.find_element(By.CSS_SELECTOR, '[data-testid="registered_year"]').text
                year = raw_year.split(" ")[0] 
            except:
                year = "N/A"
                
            try:
                price = card.find_element(By.XPATH, './/span[contains(text(), "£")]').text
            except:
                price = "N/A"
                
            # --- GET THE IMAGE ---
            try:
                image_el = card.find_element(By.CSS_SELECTOR, 'picture source')
                image_url = image_el.get_attribute('srcset')
            except:
                image_url = "N/A"

            # ==========================================
            # DATA CLEANUP: Convert to Integers
            # ==========================================
            
            # Remove everything except digits, then convert to int. Fallback to None if "N/A"
            clean_price = int(re.sub(r'[^\d]', '', price)) if price != "N/A" else None
            clean_mileage = int(re.sub(r'[^\d]', '', mileage)) if mileage != "N/A" else None
            clean_year = int(year) if year != "N/A" else None

            # ==========================================

            car_info = {
                "title": raw_title.split('\n')[0],
                "trim": trim,
                "price": clean_price,
                "mileage": clean_mileage,
                "year": clean_year,
                "image_url": image_url,
                "link": title_el.get_attribute("href")
            }
            
            scraped_cars.append(car_info)
            # Format the print statement so it looks nice in the console even though they are now ints
            print(f"✅ Found: {car_info['title']} | £{clean_price} | {clean_year} | Image OK")
            
        except Exception as extract_error:
            print(f"--> Skipped a card due to extraction error: {extract_error}")
            
    return scraped_cars