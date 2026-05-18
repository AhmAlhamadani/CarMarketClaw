import time
from datetime import datetime, UTC

from api.db.supabase_client import supabase
from clawbot.vision import build_vision_context

from clawbot.agents.vehicle_detector import detect_vehicle
from clawbot.agents.scam_detector import detect_scam
from clawbot.agents.damage_detector import detect_damage
from clawbot.agents.plate_reader import read_plate


def fetch_jobs():
    result = (
        supabase
        .table("fb_vehicles")
        .select("*")
        .is_("ai_last_updated", "null")
        .limit(5)
        .execute()
    )
    return result.data


def process_vehicle(vehicle):
    print(f"\nProcessing: {vehicle['title']}")
    print("Building vision context...")

    vision = build_vision_context(vehicle["image_urls"])

    print(f"{len(vision['images'])} images loaded")

    updates = {}

    # Vision agents
    updates.update(detect_vehicle(vehicle, vision))
    updates.update(detect_damage(vehicle, vision))
    updates.update(read_plate(vision))

    # Text agents
    updates.update(detect_scam(vehicle))


    updates["ai_last_updated"] = datetime.now(UTC).isoformat()

    (
        supabase
        .table("fb_vehicles")
        .update(updates)
        .eq("id", vehicle["id"])
        .execute()
    )

    print("Done")


def run():
    while True:
        jobs = fetch_jobs()

        if not jobs:
            print("No jobs.")
            time.sleep(10)
            continue

        for job in jobs:
            process_vehicle(job)


if __name__ == "__main__":
    run()