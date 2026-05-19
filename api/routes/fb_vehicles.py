from fastapi import APIRouter

from api.db.at_vehicles_repo import list_by_fb_vehicle_id
from api.db.fb_vehicles_repo import (
    get_by_id,
    list_pending_completion,
    list_pending_enrichment,
    save_scraped_vehicle,
)

router = APIRouter()


@router.post("/")
def create_fb_vehicle(vehicle: dict):
    saved = save_scraped_vehicle(vehicle)
    return {"message": "vehicle saved", "vehicle": saved}


@router.get("/pending_enrichment")
def get_pending_enrichment():
    """All fb_vehicles rows where ai_last_updated is null."""
    vehicles = list_pending_enrichment()
    return {"count": len(vehicles), "vehicles": vehicles}


@router.get("/pending_completion")
def get_pending_completion():
    """All fb_vehicles rows where completed is false (AutoTrader not run yet)."""
    vehicles = list_pending_completion()
    return {"count": len(vehicles), "vehicles": vehicles}


@router.get("/{vehicle_id}")
def get_fb_vehicle(vehicle_id: str):
    """Single Facebook listing by id, including saved AutoTrader matches."""
    vehicle = get_by_id(vehicle_id)
    return {
        "vehicle": vehicle,
        "autotrader_matches": list_by_fb_vehicle_id(vehicle_id),
    }
