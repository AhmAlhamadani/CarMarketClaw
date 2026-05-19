from api.db.supabase_client import supabase

from systems.vision import (
    build_vision_context
)

from systems.agents.vehicle_detector import (
    detect_vehicle
)


print("Fetching vehicle...")


row = (
    supabase
    .table("fb_vehicles")
    .select("*")
    .limit(1)
    .execute()
)


vehicle = row.data[0]


print(
    f"Title: {vehicle['title']}"
)


print(
    "Building vision context..."
)


vision = build_vision_context(
    vehicle["image_urls"]
)


print(
    "Running vehicle detector..."
)


result = detect_vehicle(
    vehicle,
    vision
)


print(
    "Result:"
)


print(
    result
)