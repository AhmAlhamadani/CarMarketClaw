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

MARKETPLACE_URL = "https://www.facebook.com/marketplace/glasgow/search?maxPrice=5000&daysSinceListed=2&minYear=2005&topLevelVehicleType=car_truck&query=Vehicles&category_id=546583916084032&exact=false&referral_ui_component=category_menu_item&locale=en_GB"
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


_PRODUCT_PHOTO_ALT = re.compile(r"^Product photo of\s+(.+)$", re.IGNORECASE)

_MULTI_WORD_MAKES = (
    "land rover", "aston martin", "rolls royce", "alfa romeo", "mercedes benz",
    "mercedes-benz", "range rover", "great wall",
)


def _split_make_model(text: str) -> tuple[str, str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return "Unknown", "Unknown"

    lower = text.lower()
    for phrase in sorted(_MULTI_WORD_MAKES, key=len, reverse=True):
        if lower.startswith(phrase + " "):
            rest = text[len(phrase) :].strip()
            return phrase.title(), rest or "Unknown"
        if lower == phrase:
            return phrase.title(), "Unknown"

    parts = text.split(None, 1)
    return parts[0].title(), (parts[1] if len(parts) > 1 else "Unknown")


def _normalize_model(make: str, model: str) -> str:
    """Strip duplicated make prefix unless the remainder is only a digit (e.g. Mazda 2)."""
    if not make or not model or model == "Unknown":
        return model
    if model.lower().startswith(make.lower()):
        trimmed = model[len(make) :].strip()
        if trimmed and not trimmed.isdigit():
            return trimmed
    return model


def parse_title(title_text):
    if not title_text:
        return 0, "Unknown", "Unknown"

    title_text = title_text.strip().split("·")[0].strip()
    title_text = re.sub(r"\s+", " ", title_text)

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", title_text)
    if not year_match:
        return 0, "Unknown", title_text

    year = int(year_match.group(1))
    if year < 1950 or year > datetime.now().year + 1:
        return 0, "Unknown", title_text

    without_year = (title_text[: year_match.start()] + title_text[year_match.end() :]).strip()
    without_year = re.sub(r"\s+", " ", without_year)
    if not without_year:
        return year, "Unknown", title_text

    make, model = _split_make_model(without_year)
    model = _normalize_model(make, model)
    return year, make, model


def _title_from_product_photo_alt(alt: str) -> str | None:
    match = _PRODUCT_PHOTO_ALT.match((alt or "").strip())
    return match.group(1).strip() if match else None


def _extract_listing_title(sb) -> str | None:
    """Mac/Windows Marketplace: title in h1 > span, or img[alt^='Product photo of']."""
    try:
        sb.wait_for_element("h1", timeout=15)
        h1 = sb.find_element("h1")
        text = (h1.text or "").strip()
        if text and text.lower() != "unknown":
            return text.split("·")[0].strip()
    except Exception:
        pass

    try:
        for img in sb.find_elements('img[alt*="Product photo"]'):
            alt_title = _title_from_product_photo_alt(img.get_attribute("alt") or "")
            if alt_title:
                return alt_title
    except Exception:
        pass

    try:
        page_title = (sb.driver.title or "").strip()
        if page_title and "facebook" not in page_title.lower():
            return page_title.split("|")[0].strip()
    except Exception:
        pass

    return None


def _apply_title(vehicle: dict, title: str) -> None:
    vehicle["title"] = title
    year, make, model = parse_title(title)
    vehicle["year"] = year
    vehicle["make"] = make
    vehicle["model"] = model


def clean_images(images):
    cleaned = []
    for src in images:
        if not src or src.startswith("data:image") or "play_48dp.png" in src:
            continue
        if "s32x32" in src or "p50x50" in src or "static_map.php" in src:
            continue
        cleaned.append(src)
    return list(set(cleaned))


_BANNED_TITLE_KEYWORDS = [
    "tops prices", "buying cars", "wanted", "finance", "breaking", "spares", "parts",
]


def invalid_vehicle_reason(v) -> str | None:
    title = (v.get("title") or "").strip()
    title_lower = title.lower()

    if not title or title_lower == "unknown":
        return "title_not_found"
    if any(b in title_lower for b in _BANNED_TITLE_KEYWORDS):
        return "banned_keywords"
    if v["year"] < 1950 or v["year"] > datetime.now().year + 1:
        return "invalid_year"
    if v["make"] in ["Unknown", "", None]:
        return "make_not_parsed"
    return None


def is_valid_vehicle(v):
    return invalid_vehicle_reason(v) is None


def should_mark_skipped_as_seen(reason: str) -> bool:
    return reason == "banned_keywords"


# ----------------------------
# SCRAPING HELPERS
# ----------------------------

def scroll_to_load_listings(sb, scroll_count=8):
    print("⏳ Scrolling Marketplace naturally...")
    for i in range(scroll_count):
        # Optimization: Stop scrolling if we've hit the "outside your search" boundary
        try:
            if sb.is_element_present('//span[contains(text(), "Results from outside your search")]'):
                print("🛑 Reached 'outside your search' boundary. Stopping scroll early.")
                break
        except Exception:
            pass

        scroll_amount = random.randint(400, 900)
        sb.execute_script(f"window.scrollBy(0, {scroll_amount});")
        # Random pause between scrolls
        human_sleep(1.2, 3.5)
        print(f"   Scroll {i+1}/{scroll_count}")


def get_organic_urls(sb):
    print("🔍 Filtering listings...")
    
    # 1. Find the Y-coordinate of the divider (if it exists)
    divider_y = float('inf')
    try:
        # Use a short timeout so we don't stall if the text isn't on the page yet
        divider = sb.find_element('//span[contains(text(), "Results from outside your search")]', timeout=1)
        if divider:
            divider_y = divider.location['y']
            print(f"📍 Found 'outside search' boundary at Y:{divider_y}. Skipping items below this.")
    except Exception:
        # If the text isn't found, all results currently loaded are likely local
        pass

    links = sb.find_elements('a')
    urls = []
    for link in links:
        try:
            href = link.get_attribute("href")
            if not href or "/marketplace/item/" not in href:
                continue
            
            # 2. Skip any listings rendered physically below the divider
            if link.location['y'] > divider_y:
                continue
                
            text = link.text.lower()
            if "sponsored" in text or "ad" in text:
                continue
                
            clean = href.split("?")[0]
            if clean not in urls:
                urls.append(clean)
        except Exception:
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

    title = _extract_listing_title(sb)
    if title:
        _apply_title(vehicle, title)

    for price_xpath in (
        '//h1/following::span[contains(text(),"£")][1]',
        '//span[contains(text(),"£")][1]',
    ):
        try:
            price_text = sb.get_text(price_xpath)
            if price_text and "£" in price_text:
                vehicle["price"] = extract_first_integer(price_text)
                break
        except Exception:
            continue

    try:
        imgs = sb.find_elements('img[alt*="Product photo"]')
        urls = [img.get_attribute("src") for img in imgs if img.get_attribute("src")]
        vehicle["image_urls"] = clean_images(urls)
    except:
        pass

    for desc_xpath in (
        '//h2[contains(., "Seller") and contains(., "description")]/following::span[@dir="auto"][1]',
        '//h2[contains(., "description")]/following::span[@dir="auto"][1]',
    ):
        try:
            desc_element = sb.find_element(desc_xpath)
            if desc_element and desc_element.text.strip():
                vehicle["description"] = desc_element.text.strip()
                break
        except Exception:
            continue

    try:
        seller_elements = sb.find_elements('a[href*="/marketplace/profile/"]')
        for elem in seller_elements:
            aria = (elem.get_attribute("aria-label") or "").strip()
            if aria and aria.lower() not in ("seller details", "see profile"):
                vehicle["seller_name"] = aria
                break
            text = elem.text.strip().split("\n")[0]
            if text and text.lower() not in ["seller details", "message", "see profile"]:
                vehicle["seller_name"] = text
                break
    except Exception:
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

            elif "fuel type" in tl or ("fuel" in tl and ":" in t):
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
    except Exception:
        pass

    if vehicle["description"]:
        desc_lower = vehicle["description"].lower()
        if vehicle["fuel_type"] == "other":
            if "petrol" in desc_lower or "gasoline" in desc_lower:
                vehicle["fuel_type"] = "petrol"
            elif "diesel" in desc_lower:
                vehicle["fuel_type"] = "diesel"
            elif "hybrid" in desc_lower:
                vehicle["fuel_type"] = "hybrid"
            elif "electric" in desc_lower:
                vehicle["fuel_type"] = "electric"

        if vehicle["engine_size"] is None or vehicle["engine_size"] <= 0:
            try:
                fallback_match = re.search(
                    r"(\d+(?:\.\d+)?)\s*(?:litre|liter|\bl\b)", desc_lower
                )
                if fallback_match:
                    parsed_val = float(fallback_match.group(1))
                    if 0.5 <= parsed_val <= 8.0:
                        vehicle["engine_size"] = parsed_val
            except Exception:
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
        "skipped_parse": 0,
        "api_errors": 0,
        "errors": 0,
        "vehicles": [],
    }

    print(f"Loading profile: {PROFILE_DIR}")

    seen_listings = load_seen_listings()
    print(f"📂 Loaded {len(seen_listings)} previously scraped listings.")

    with SB(uc=True, user_data_dir=PROFILE_DIR, headed=True) as sb:
        try:
            sb.set_window_size(1400, 900)
        except Exception:
            pass
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

                reason = invalid_vehicle_reason(data)
                if reason:
                    preview = data.get("title") or url
                    if should_mark_skipped_as_seen(reason):
                        print(f"❌ Skipping junk ({reason}): {preview}")
                        mark_as_seen(seen_listings, fb_id)
                        stats["skipped_invalid"] += 1
                    else:
                        print(f"⚠️ Skipping for retry ({reason}): {preview}")
                        stats["skipped_parse"] += 1
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