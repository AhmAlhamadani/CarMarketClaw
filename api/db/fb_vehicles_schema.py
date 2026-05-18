"""Column sets and normalizers aligned with public.fb_vehicles."""

SCRAPER_FIELDS = frozenset({
    "fb_id",
    "source_url",
    "title",
    "location",
    "make",
    "model",
    "year",
    "price",
    "mileage",
    "image_urls",
    "transmission",
    "fuel_type",
    "seller_name",
    "seller_join_date",
    "description",
    "engine_size",
    "exterior_colour",
    "interior_colour",
    "clean_title",
    "vehicle_condition",
})

VEHICLE_AGENT_FIELDS = frozenset({
    "is_car_ai",
    "is_car_ai_confidence",
})

SCAM_AGENT_FIELDS = frozenset({
    "scam_risk_score",
    "scam_risk_level",
    "scam_risk_explanation",
    "scam_risk_confidence",
})

DAMAGE_AGENT_FIELDS = frozenset({
    "damage_ai",
    "damage_explanation_ai",
    "damage_ai_confidence",
})

PLATE_AGENT_FIELDS = frozenset({
    "carplate_ai",
    "carplate_ai_confidence",
})

TRANSMISSION_VALUES = frozenset({"manual", "automatic"})
FUEL_VALUES = frozenset({
    "petrol", "diesel", "gasoline", "hybrid", "electric", "plug_in_hybrid", "other",
})
CONDITION_VALUES = frozenset({"excellent", "very_good", "good", "fair", "poor"})

REQUIRED_SCRAPER_FIELDS = frozenset({
    "title",
    "location",
    "make",
    "model",
    "year",
    "price",
    "mileage",
    "image_urls",
    "transmission",
    "fuel_type",
    "seller_name",
    "seller_join_date",
})


def pick(data: dict, allowed: frozenset) -> dict:
    return {key: data[key] for key in allowed if key in data}


def _to_int(value, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(value)


def normalize_scraper_row(data: dict) -> dict:
    row = pick(data, SCRAPER_FIELDS)

    for field in ("year", "price", "mileage", "seller_join_date"):
        if field in row:
            row[field] = _to_int(row[field])

    if "engine_size" in row and row["engine_size"] is not None:
        row["engine_size"] = float(row["engine_size"])

    if "image_urls" in row:
        row["image_urls"] = list(row["image_urls"] or [])

    if row.get("transmission") not in TRANSMISSION_VALUES:
        row["transmission"] = "manual"

    if row.get("fuel_type") not in FUEL_VALUES:
        row["fuel_type"] = "other"

    condition = row.get("vehicle_condition")
    if condition is not None and condition not in CONDITION_VALUES:
        row.pop("vehicle_condition", None)

    if row.get("description") == "":
        row["description"] = None

    return row


def normalize_agent_row(data: dict, allowed: frozenset) -> dict:
    row = pick(data, allowed)

    if "is_car_ai" in row:
        row["is_car_ai"] = bool(row["is_car_ai"])
    if "damage_ai" in row:
        row["damage_ai"] = bool(row["damage_ai"])

    return row


def missing_required_fields(row: dict) -> list[str]:
    missing = []
    for field in REQUIRED_SCRAPER_FIELDS:
        value = row.get(field)
        if value is None:
            missing.append(field)
        elif field == "image_urls" and not value:
            missing.append(field)
        elif field in ("title", "location", "make", "model", "seller_name") and value == "":
            missing.append(field)
    return missing
