from fastapi import APIRouter

from api.db.fb_vehicles_repo import get_by_id, save_agent_result
from api.db.fb_vehicles_schema import (
    VEHICLE_AGENT_FIELDS,
    SCAM_AGENT_FIELDS,
    DAMAGE_AGENT_FIELDS,
    PLATE_AGENT_FIELDS,
)
from clawbot.vision import build_vision_context
from clawbot.agents.vehicle_detector import detect_vehicle
from clawbot.agents.scam_detector import detect_scam
from clawbot.agents.damage_detector import detect_damage
from clawbot.agents.plate_reader import read_plate

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
