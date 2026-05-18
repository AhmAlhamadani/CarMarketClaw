"""Column sets and normalizers aligned with public.at_vehicles."""

AT_VEHICLE_FIELDS = frozenset({
    "fb_vehicle_id",
    "title",
    "trim",
    "price",
    "mileage",
    "year",
    "image_url",
    "link",
})

REQUIRED_AT_FIELDS = frozenset({"title"})


def pick(data: dict, allowed: frozenset) -> dict:
    return {key: data[key] for key in allowed if key in data}


def _first_image_url(value) -> str | None:
    if not value or value == "N/A":
        return None
    if isinstance(value, str) and " " in value:
        return value.split()[0].strip()
    return str(value)


def normalize_at_row(car: dict, fb_vehicle_id: str) -> dict:
    trim = car.get("trim")
    if trim in (None, "", "N/A"):
        trim = None

    row = {
        "fb_vehicle_id": fb_vehicle_id,
        "title": (car.get("title") or "").strip(),
        "trim": trim,
        "price": car.get("price"),
        "mileage": car.get("mileage"),
        "year": car.get("year"),
        "image_url": _first_image_url(car.get("image_url")),
        "link": car.get("link"),
    }
    return pick(row, AT_VEHICLE_FIELDS | {"fb_vehicle_id"})


def missing_required_fields(row: dict) -> list[str]:
    missing = []
    for field in REQUIRED_AT_FIELDS:
        value = row.get(field)
        if value is None or value == "":
            missing.append(field)
    return missing
