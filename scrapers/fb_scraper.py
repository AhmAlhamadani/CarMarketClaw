import os
import sys
import time
import re
import requests
import random
import json
from datetime import datetime
from seleniumbase import SB

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(SCRIPT_DIR, "stealth_profile")
SEEN_LISTINGS_FILE = os.path.join(SCRIPT_DIR, "seen_listings.json")

MARKETPLACE_URL = "https://www.facebook.com/marketplace/glasgow/search?daysSinceListed=2&query=Vehicles&category_id=546583916084032&exact=false&referral_ui_component=category_menu_item&locale=en_GB"
API_ENDPOINT = "http://localhost:8000/fb_vehicles/"


# ----------------------------
# STEALTH & STATE HELPERS
# ----------------------------

def human_sleep(min_sec=1, max_sec=5):
    """Sleeps for a random duration to mimic human pauses."""
    time.sleep(random.uniform(min_sec, max_sec))


def load_seen_listings():
    """Loads previously scraped Facebook IDs and timestamps from a local JSON file."""
    if os.path.exists(SEEN_LISTINGS_FILE):
        try:
            with open(SEEN_LISTINGS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # If the file is empty or corrupted, start fresh
            return {}
    return {}


def mark_as_seen(seen_dict, fb_id):
    """Saves a successfully scraped Facebook ID and timestamp to the local JSON file."""
    seen_dict[fb_id] = datetime.now().isoformat()
    with open(SEEN_LISTINGS_FILE, "w") as f:
        json.dump(seen_dict, f, indent=4)


def extract_id_from_url(url):
    """Quickly pull the ID from the URL before visiting it."""
    try:
        return url.split("/item/")[1].split("/")[0].split("?")[0]
    except:
        return None


# ----------------------------
# SAFE PARSERS & NORMALIZERS
# ----------------------------

def extract_first_integer(text):
    if not text:
        return 0
    match = re.search(r'(\d[\d,]*)', text)
    if not match:
        return 0
    try:
        return int(match.group(1).replace(",", ""))
    except:
        return 0


def extract_mileage(text):
    raw_val = extract_first_integer(text)
    if 0 < raw_val < 1000:
        return raw_val * 1000
    return raw_val


def parse_title(title_text):
    if not title_text:
        return 0, "Unknown", "Unknown"

    title_text = title_text.strip()
    match = re.match(r'^(19\d{2}|20\d{2})\s+([A-Za-z\-]+)\s+(.+)$', title_text, re.IGNORECASE)
    if not match:
        return 0, "Unknown", title_text

    year = int(match.group(1))
    if year > datetime.now().year + 1:
        return 0, "Unknown", title_text

    return year, match.group(2), match.group(3)


def clean_images(images):
    cleaned = []
    for src in images:
        if not src or src.startswith("data:image") or "play_48dp.png" in src:
            continue
        if "s32x32" in src or "p50x50" in src or "static_map.php" in src:
            continue
        cleaned.append(src)
    return list(set(cleaned))


def is_valid_vehicle(v):
    title = (v.get("title") or "").lower()
    banned = ["tops prices", "buying cars", "wanted", "finance", "breaking", "spares", "parts"]

    if any(b in title for b in banned):
        return False
    if v["year"] < 1950 or v["year"] > datetime.now().year + 1:
        return False
    if v["make"] in ["Unknown", "", None]:
        return False
    return True


# ----------------------------
# SCRAPING HELPERS
# ----------------------------

def scroll_to_load_listings(sb, scroll_count=8):
    print("⏳ Scrolling Marketplace naturally...")
    for i in range(scroll_count):
        scroll_amount = random.randint(400, 900)
        sb.execute_script(f"window.scrollBy(0, {scroll_amount});")
        
        # Random pause between scrolls
        human_sleep(1.2, 3.5)
        print(f"   Scroll {i+1}/{scroll_count}")


def get_organic_urls(sb):
    print("🔍 Filtering listings...")
    links = sb.find_elements('a')
    urls = []

    for link in links:
        try:
            href = link.get_attribute("href")
            if not href or "/marketplace/item/" not in href:
                continue

            text = link.text.lower()
            if "sponsored" in text or "ad" in text:
                continue

            clean = href.split("?")[0]
            if clean not in urls:
                urls.append(clean)
        except:
            continue
    return urls


# ----------------------------
# SCRAPER CORE
# ----------------------------

def scrape_detail_page(sb, url, fb_id):
    print(f"\n🚗 Scraping: {url}")
    sb.driver.get(url)
    
    human_sleep(3.0, 5.0)  

    vehicle = {
        "source_url": url,
        "fb_id": fb_id,
        "title": "Unknown",
        "location": "Glasgow",
        "make": "Unknown",
        "model": "Unknown",
        "year": 0,
        "price": 0,
        "mileage": 0,
        "engine_size": None,
        "vehicle_condition": None,
        "image_urls": [],
        "transmission": "manual",
        "fuel_type": "other",
        "seller_name": "Unknown",
        "seller_join_date": 0,
        "clean_title": None,
        "description": "",
        "exterior_colour": None,
        "interior_colour": None,
    }

    try:
        title = sb.get_text("h1")
        if title:
            vehicle["title"] = title.strip()
            year, make, model = parse_title(title)
            vehicle["year"] = year
            vehicle["make"] = make
            vehicle["model"] = model
    except:
        pass

    try:
        price_text = sb.get_text('//h1/following::span[contains(text(),"£")][1]')
        if price_text:
            vehicle["price"] = extract_first_integer(price_text)
    except:
        pass

    try:
        imgs = sb.find_elements('img[alt*="Product photo"]')
        urls = [img.get_attribute("src") for img in imgs if img.get_attribute("src")]
        vehicle["image_urls"] = clean_images(urls)
    except:
        pass

    try:
        desc_element = sb.find_element('//h2[contains(., "description")]/following::span[@dir="auto"][1]')
        if desc_element:
            vehicle["description"] = desc_element.text.strip()
    except:
        pass

    try:
        seller_elements = sb.find_elements('a[href*="/marketplace/profile/"]')
        for elem in seller_elements:
            text = elem.text.strip().split("\n")[0]
            if text and text.lower() not in ["seller details", "message", "see profile"]:
                vehicle["seller_name"] = text
                break
    except:
        pass

    try:
        spans = sb.find_elements('span[dir="auto"]')
        for s in spans:
            t = s.text.strip()
            if not t:
                continue
            tl = t.lower()

            if "driven" in tl:
                vehicle["mileage"] = extract_mileage(t)

            elif "transmission" in tl:
                if "automatic" in tl:
                    vehicle["transmission"] = "automatic"
                elif "manual" in tl:
                    vehicle["transmission"] = "manual"

            elif "fuel type" in tl or "fuel" in tl:
                fuel = t.split(":")[-1].strip().lower().replace(" ", "_")
                if "petrol" in fuel:
                    vehicle["fuel_type"] = "petrol"
                elif "diesel" in fuel:
                    vehicle["fuel_type"] = "diesel"
                elif fuel in ["gasoline", "hybrid", "electric", "plug_in_hybrid", "other"]:
                    vehicle["fuel_type"] = fuel
                else:
                    vehicle["fuel_type"] = "other"

            elif "engine size" in tl:
                eng_match = re.search(r'(-?\d+(?:\.\d+)?)', tl)
                if eng_match:
                    val = float(eng_match.group(1))
                    if val > 0:
                        vehicle["engine_size"] = val

            elif "condition" in tl:
                if "like new" in tl or "excellent" in tl:
                    vehicle["vehicle_condition"] = "excellent"
                elif "very good" in tl:
                    vehicle["vehicle_condition"] = "very_good"
                elif "good" in tl:
                    vehicle["vehicle_condition"] = "good"
                elif "fair" in tl:
                    vehicle["vehicle_condition"] = "fair"
                elif "poor" in tl:
                    vehicle["vehicle_condition"] = "poor"

            elif "clean title" in tl or ("title" in tl and "clean" in tl):
                vehicle["clean_title"] = True

            elif "joined facebook in" in tl:
                join_year = extract_first_integer(t)
                if 2004 <= join_year <= datetime.now().year:
                    vehicle["seller_join_date"] = join_year

            elif "listed in" in tl:
                vehicle["location"] = t.split("in")[-1].strip()

            elif "exterior color" in tl or "exterior colour" in tl:
                parts = t.split("·")
                for p in parts:
                    pl = p.lower()
                    if "exterior" in pl:
                        vehicle["exterior_colour"] = p.split(":")[-1].strip()
                    if "interior" in pl:
                        vehicle["interior_colour"] = p.split(":")[-1].strip()
    except:
        pass

    if (vehicle["engine_size"] is None or vehicle["engine_size"] <= 0) and vehicle["description"]:
        try:
            desc_lower = vehicle["description"].lower()
            fallback_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:litre|liter|\bl\b)', desc_lower)
            if fallback_match:
                parsed_val = float(fallback_match.group(1))
                if 0.5 <= parsed_val <= 8.0: 
                    vehicle["engine_size"] = parsed_val
        except:
            pass

    return vehicle


# ----------------------------
# MAIN PROCESSING LOOP
# ----------------------------

def run(interactive_login: bool | None = None) -> dict:
    """Run a full Marketplace scan. Blocks until every listing on the page is processed."""
    if interactive_login is None:
        interactive_login = sys.stdin.isatty()

    stats = {
        "status": "completed",
        "found": 0,
        "saved": 0,
        "skipped_seen": 0,
        "skipped_invalid": 0,
        "api_errors": 0,
        "errors": 0,
        "vehicles": [],
    }

    print(f"Loading profile: {PROFILE_DIR}")

    seen_listings = load_seen_listings()
    print(f"📂 Loaded {len(seen_listings)} previously scraped listings.")

    with SB(uc=True, user_data_dir=PROFILE_DIR, headed=True) as sb:
        sb.driver.get(MARKETPLACE_URL)
        human_sleep(3.0, 6.0)

        if "login" in sb.get_current_url():
            if interactive_login:
                input("👉 Log in then press ENTER...")
                time.sleep(5)
            else:
                stats["status"] = "login_required"
                return stats

        scroll_to_load_listings(sb)
        urls = get_organic_urls(sb)
        stats["found"] = len(urls)
        print(f"📦 Found {len(urls)} listings on page.")

        for url in urls:
            fb_id = extract_id_from_url(url)

            if not fb_id or fb_id in seen_listings:
                print(f"⏭️ Skipping already seen or invalid ID: {fb_id}")
                stats["skipped_seen"] += 1
                continue

            try:
                data = scrape_detail_page(sb, url, fb_id)

                if not is_valid_vehicle(data):
                    print(f"❌ Skipping junk: {data['title']}")
                    mark_as_seen(seen_listings, fb_id)
                    stats["skipped_invalid"] += 1
                    continue

                print(
                    f"📤 Sending: {data['fb_id']} | {data['title']} | "
                    f"Mileage: {data['mileage']} km | Condition: {data['vehicle_condition']}"
                )
                res = requests.post(API_ENDPOINT, json=data, timeout=10)

                if res.status_code in [200, 201]:
                    print("✅ Saved Successfully")
                    mark_as_seen(seen_listings, fb_id)
                    stats["saved"] += 1
                    body = res.json()
                    saved = body.get("vehicle") or {}
                    stats["vehicles"].append(saved)
                else:
                    print(f"❌ API Error {res.status_code}: {res.text}")
                    print(data)
                    stats["api_errors"] += 1

            except Exception as e:
                print(f"⚠️ Error processing page {url}: {e}")
                stats["errors"] += 1

            human_sleep(2.0, 4.5)

    return stats


if __name__ == "__main__":
    run()