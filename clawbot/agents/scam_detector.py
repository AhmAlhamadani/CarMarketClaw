import re
from datetime import datetime, UTC

# Phrases that strongly indicate a scam (deposits, off-platform communication)
SCAM_KEYWORDS_HIGH = [
    r"western union", r"gift card", r"crypto", r"bitcoin", r"pay in advance",
    r"send deposit", r"holding fee", r"wire transfer", r"email me at",
    r"contact me outside", r"shipping company will", r"escrow company"
]

# Phrases often used in scam "sob stories" to explain a cheap price
SCAM_KEYWORDS_MEDIUM = [
    r"moving abroad", r"selling for a friend", r"military deployment",
    r"urgent sale", r"out of country", r"widow", r"divorce", r"selling on behalf"
]

def detect_scam(vehicle):
    description = (vehicle.get("description") or "").lower()
    title = (vehicle.get("title") or "").lower()
    text = f"{title} {description}"
    
    score = 0.0
    explanations = []

    # --- 1. Keyword Analysis ---
    high_risk_hits = [kw for kw in SCAM_KEYWORDS_HIGH if re.search(kw, text)]
    if high_risk_hits:
        score += 0.4 * len(high_risk_hits)
        explanations.append(f"High-risk phrases found: {', '.join(high_risk_hits)}")

    medium_risk_hits = [kw for kw in SCAM_KEYWORDS_MEDIUM if re.search(kw, text)]
    if medium_risk_hits:
        score += 0.15 * len(medium_risk_hits)
        explanations.append(f"Suspicious context phrases found: {', '.join(medium_risk_hits)}")

    # --- 2. Seller Join Date Analysis ---
    join_date_str = vehicle.get("seller_join_date")
    if join_date_str:
        try:
            join_date_str = str(join_date_str).lower()
            current_year = datetime.now(UTC).year
            
            # Handle FB format like "2024" or "Joined in 2024"
            year_match = re.search(r'\d{4}', join_date_str)
            if year_match:
                join_year = int(year_match.group())
                if current_year - join_year == 0:
                    score += 0.3
                    explanations.append("Seller account is brand new (joined this year).")
                elif current_year - join_year == 1:
                    score += 0.1
                    explanations.append("Seller account is relatively new (joined last year).")
            # Handle ISO datetime format if your scraper provides exact dates
            elif "T" in join_date_str or "-" in join_date_str:
                 join_date = datetime.fromisoformat(join_date_str.replace('Z', '+00:00'))
                 days_active = (datetime.now(UTC) - join_date).days
                 if days_active < 30:
                     score += 0.4
                     explanations.append("Seller account is extremely new (< 30 days old).")
        except Exception:
            pass # Silently ignore parsing errors to prevent crashing the pipeline

    # --- 3. Price Analysis ---
    price = vehicle.get("price")
    if price is not None:
        try:
            # Strip currency symbols and commas
            clean_price = re.sub(r'[^0-9.]', '', str(price))
            p = float(clean_price)
            if 0 < p < 500: # Suspiciously cheap for a car
                score += 0.2
                explanations.append(f"Price ({price}) is suspiciously low for a vehicle.")
            elif p in [1234, 12345, 1111]: # Common placeholder prices for sketchy listings
                score += 0.1
                explanations.append(f"Price ({price}) looks like a placeholder.")
        except ValueError:
            pass

    # --- 4. Final Scoring ---
    score = min(score, 1.0) # Cap at 1.0 (100%)

    if score >= 0.7:
        level = "high"
    elif score >= 0.4:
        level = "medium"
    else:
        level = "low"

    if score == 0.0:
        explanations.append("No obvious suspicious indicators found.")

    return {
        "scam_risk_score": round(score, 2),
        "scam_risk_level": level,
        "scam_risk_explanation": " | ".join(explanations),
        "scam_risk_confidence": 0.85 # Rule-based heuristics are generally highly confident
    }