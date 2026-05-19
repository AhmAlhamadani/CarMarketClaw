from fastapi import APIRouter, HTTPException

from api.db.fb_vehicles_repo import get_by_id, save_agent_result
from api.db.fb_vehicles_schema import (
    VEHICLE_AGENT_FIELDS,
    SCAM_AGENT_FIELDS,
    DAMAGE_AGENT_FIELDS,
    PLATE_AGENT_FIELDS,
)
from systems.vision import build_vision_context
from systems.agents.vehicle_detector import detect_vehicle
from systems.agents.scam_detector import detect_scam
from systems.agents.damage_detector import detect_damage
from systems.agents.plate_reader import read_plate

router = APIRouter()


def _vision_for(vehicle: dict) -> dict:
    print("  Building vision context...")
    vision = build_vision_context(vehicle.get("image_urls") or [])
    print(f"  Loaded {len(vision.get('images', []))} images")
    return vision


def _run_agent(vehicle_id: str, agent_name: str, allowed_fields: frozenset, result: dict) -> dict:
    print(f"  Running {agent_name}...")
    vehicle = save_agent_result(vehicle_id, result, allowed_fields)
    print(f"✅ {agent_name} finished for {vehicle_id}")
    return {
        "message": "agent result saved",
        "agent_result": {k: vehicle[k] for k in allowed_fields if k in vehicle},
        "vehicle": vehicle,
    }


@router.api_route("/vehicle/{vehicle_id}", methods=["GET", "POST"])
def run_vehicle_detector(vehicle_id: str):
    print(f"▶ Starting vehicle detector | id={vehicle_id}")
    vehicle = get_by_id(vehicle_id)
    print(f"  Listing: {vehicle.get('title')}")
    vision = _vision_for(vehicle)
    return _run_agent(vehicle_id, "vehicle detector", VEHICLE_AGENT_FIELDS, detect_vehicle(vehicle, vision))


@router.api_route("/scam/{vehicle_id}", methods=["GET", "POST"])
def run_scam_detector(vehicle_id: str):
    print(f"▶ Starting scam detector | id={vehicle_id}")
    vehicle = get_by_id(vehicle_id)
    print(f"  Listing: {vehicle.get('title')}")
    return _run_agent(vehicle_id, "scam detector", SCAM_AGENT_FIELDS, detect_scam(vehicle))


@router.api_route("/damage/{vehicle_id}", methods=["GET", "POST"])
def run_damage_detector(vehicle_id: str):
    print(f"▶ Starting damage detector | id={vehicle_id}")
    vehicle = get_by_id(vehicle_id)
    print(f"  Listing: {vehicle.get('title')}")
    vision = _vision_for(vehicle)
    return _run_agent(vehicle_id, "damage detector", DAMAGE_AGENT_FIELDS, detect_damage(vehicle, vision))


@router.api_route("/plate/{vehicle_id}", methods=["GET", "POST"])
def run_plate_reader(vehicle_id: str):
    print(f"▶ Starting plate reader | id={vehicle_id}")
    vehicle = get_by_id(vehicle_id)
    print(f"  Listing: {vehicle.get('title')}")
    vision = _vision_for(vehicle)
    return _run_agent(vehicle_id, "plate reader", PLATE_AGENT_FIELDS, read_plate(vision))


_ALL_AGENT_FIELDS = (
    PLATE_AGENT_FIELDS
    | VEHICLE_AGENT_FIELDS
    | DAMAGE_AGENT_FIELDS
    | SCAM_AGENT_FIELDS
)


@router.api_route("/enrich_car/{vehicle_id}", methods=["GET", "POST"])
def enrich_car(vehicle_id: str):
    """Run plate, vehicle, damage, and scam agents in order. Only when ai_last_updated is null."""
    vehicle = get_by_id(vehicle_id)
    if vehicle.get("ai_last_updated") is not None:
        raise HTTPException(
            status_code=409,
            detail="Vehicle already enriched (ai_last_updated is set)",
        )

    print(f"▶ Starting enrich_car | id={vehicle_id}")
    print(f"  Listing: {vehicle.get('title')}")
    vision = _vision_for(vehicle)

    steps = [
        ("plate reader", PLATE_AGENT_FIELDS, lambda: read_plate(vision)),
        ("vehicle detector", VEHICLE_AGENT_FIELDS, lambda: detect_vehicle(vehicle, vision)),
        ("damage detector", DAMAGE_AGENT_FIELDS, lambda: detect_damage(vehicle, vision)),
        ("scam detector", SCAM_AGENT_FIELDS, lambda: detect_scam(vehicle)),
    ]

    agent_results = {}
    for index, (agent_name, fields, run) in enumerate(steps):
        print(f"  Running {agent_name}...")
        result = run()
        touch = index == len(steps) - 1
        vehicle = save_agent_result(
            vehicle_id, result, fields, touch_ai_last_updated=touch
        )
        agent_results[agent_name] = {k: vehicle[k] for k in fields if k in vehicle}
        print(f"✅ {agent_name} finished for {vehicle_id}")

    print(f"✅ enrich_car complete for {vehicle_id}")
    return {
        "message": "vehicle enriched",
        "agent_results": agent_results,
        "vehicle": vehicle,
        "agent_result": {k: vehicle[k] for k in _ALL_AGENT_FIELDS if k in vehicle},
    }
