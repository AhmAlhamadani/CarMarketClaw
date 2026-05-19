from datetime import datetime, UTC
from systems.agents.scam_detector import detect_scam

def run_tests():
    # Helper to get the current year for the "new account" logic
    current_year = datetime.now(UTC).year

    print("--- Running Scam Detector Tests ---\n")

    # TEST 1: HIGH RISK (Crypto, new account, suspiciously cheap)
    high_risk_vehicle = {
        "id": "1",
        "title": "2020 BMW 3 Series - URGENT SALE",
        "description": "Moving abroad next week. Send deposit via Western Union or Bitcoin. Email me at scammer@email.com",
        "price": "£450",  # Suspiciously low
        "seller_join_date": f"{current_year}" # Brand new account
    }

    # TEST 2: MEDIUM RISK (Sob story, placeholder price, 1-year-old account)
    medium_risk_vehicle = {
        "id": "2",
        "title": "Ford Fiesta 2015",
        "description": "Selling on behalf of my uncle. Military deployment coming up soon so need it gone.",
        "price": "£1234", # Placeholder price
        "seller_join_date": f"{current_year - 1}" # 1 year old
    }

    # TEST 3: LOW RISK / SAFE (Normal listing)
    safe_vehicle = {
        "id": "3",
        "title": "2018 Honda Civic 1.5 VTEC",
        "description": "Great condition, full service history, MOT until next year. Viewings welcome.",
        "price": "£12,500",
        "seller_join_date": "2015" # Old, established account
    }

    # TEST 4: EDGE CASE (Missing fields, empty descriptions)
    edge_case_vehicle = {
        "id": "4"
        # No title, description, price, or join date
    }

    tests = [
        ("High Risk Test", high_risk_vehicle),
        ("Medium Risk Test", medium_risk_vehicle),
        ("Safe Listing Test", safe_vehicle),
        ("Missing Data Edge Case", edge_case_vehicle)
    ]

    for test_name, vehicle_data in tests:
        print(f"=== {test_name} ===")
        result = detect_scam(vehicle_data)
        
        print(f"Risk Level: {result['scam_risk_level'].upper()}")
        print(f"Score:      {result['scam_risk_score']}")
        print(f"Confidence: {result['scam_risk_confidence']}")
        print(f"Notes:      {result['scam_risk_explanation']}\n")

if __name__ == "__main__":
    run_tests()