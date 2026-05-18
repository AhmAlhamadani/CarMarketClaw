from fastapi import APIRouter, HTTPException

from api.db.supabase_client import supabase
from clawbot.vision import build_vision_context
from clawbot.agents.vehicle_detector import detect_vehicle
from clawbot.agents.scam_detector import detect_scam
from clawbot.agents.damage_detector import detect_damage
from clawbot.agents.plate_reader import read_plate

router = APIRouter()


def _fetch_vehicle(vehicle_id: str) -> dict:
    response = (
        supabase.table("fb_vehicles")
        .select("*")
        .eq("id", vehicle_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return response.data[0]


def _persist(vehicle_id: str, updates: dict) -> dict:
    supabase.table("fb_vehicles").update(updates).eq("id", vehicle_id).execute()
    return {"vehicle_id": vehicle_id, "result": updates}


def _vision_for(vehicle: dict) -> dict:
    return build_vision_context(vehicle.get("image_urls") or [])


@router.post("/vehicle/{vehicle_id}")
def run_vehicle_detector(vehicle_id: str):
    """Detect whether the listing is actually a car."""
    vehicle = _fetch_vehicle(vehicle_id)
    vision = _vision_for(vehicle)
    return _persist(vehicle_id, detect_vehicle(vehicle, vision))


@router.post("/scam/{vehicle_id}")
def run_scam_detector(vehicle_id: str):
    """Score scam risk from listing text and seller metadata."""
    vehicle = _fetch_vehicle(vehicle_id)
    return _persist(vehicle_id, detect_scam(vehicle))


@router.post("/damage/{vehicle_id}")
def run_damage_detector(vehicle_id: str):
    """Detect previous or visible damage."""
    vehicle = _fetch_vehicle(vehicle_id)
    vision = _vision_for(vehicle)
    return _persist(vehicle_id, detect_damage(vehicle, vision))


@router.post("/plate/{vehicle_id}")
def run_plate_reader(vehicle_id: str):
    """Read UK registration plate from listing images."""
    vehicle = _fetch_vehicle(vehicle_id)
    vision = _vision_for(vehicle)
    return _persist(vehicle_id, read_plate(vision))
