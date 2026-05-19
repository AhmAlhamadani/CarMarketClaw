from api.db.supabase_client import supabase
from systems.vision import build_vision_context
from systems.agents.damage_detector import detect_damage

def run():
    print("Fetching vehicle...")

    row = (
        supabase
        .table("fb_vehicles")
        .select("*")
        .limit(1)
        .execute()
    )

    vehicle = row.data[0]

    print("Title:", vehicle["title"])
    print("Building vision context...")

    vision = build_vision_context(
        vehicle["image_urls"]
    )

    print("Running damage detector...")

    result = detect_damage(
        vehicle,
        vision
    )

    print("\nResult:")
    print(result)

if __name__ == "__main__":
    run()