import time
from datetime import datetime, UTC

from api.db.supabase_client import supabase

from clawbot.agents.vehicle_detector import detect_vehicle
from clawbot.agents.scam_detector import detect_scam
from clawbot.agents.colour_detector import detect_colour
from clawbot.agents.damage_detector import detect_damage
from clawbot.agents.mot_checker import check_mot
from clawbot.agents.plate_reader import read_plate
from clawbot.agents.ownership_checker import detect_owners
from clawbot.agents.service_checker import detect_service_history
from clawbot.agents.ulez_checker import check_ulez
from clawbot.agents.condition_scorer import score_condition

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

    print(f"Processing: {vehicle['title']}")

    updates = {}

    updates.update(
        detect_vehicle(vehicle["image_urls"])
    )

    updates.update(
        detect_scam(
            vehicle.get("description") or ""
        )
    )

    updates.update(
        detect_colour(
            vehicle["image_urls"]
        )
    )

    updates.update(
        detect_damage(
            vehicle["image_urls"]
        )
    )

    updates.update(
        check_mot(
            vehicle["image_urls"],
            vehicle.get("description") or ""
        )
    )

    updates.update(
        read_plate(
            vehicle["image_urls"]
        )
    )

    updates.update(
        detect_owners(
            vehicle.get("description") or ""
        )
    )

    updates.update(
        detect_service_history(
            vehicle.get("description") or ""
        )
    )

    updates.update(
        check_ulez(vehicle)
    )

    updates.update(
        score_condition(vehicle)
    )

    updates["ai_last_updated"] = (
        datetime.now(UTC).isoformat()
    )

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