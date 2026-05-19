from fastapi import APIRouter

from api.db.at_vehicles_repo import list_by_fb_vehicle_id
from api.db.fb_vehicles_repo import (
    get_by_id,
    list_pending_analysis,
    list_pending_completion,
    list_pending_enrichment,
    mark_analysed_complete,
    require_ready_for_analysis,
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
    """All fb_vehicles rows where completed_comparisons is false (AutoTrader not run yet)."""
    vehicles = list_pending_completion()
    return {"count": len(vehicles), "vehicles": vehicles}


@router.get("/pending_analysis")
def get_pending_analysis():
    """Enriched + completed_comparisons, but analysed_complete is false (ready for /analysis)."""
    vehicles = list_pending_analysis()
    return {"count": len(vehicles), "vehicles": vehicles}


@router.get("/{vehicle_id}/analysis")
def get_vehicle_analysis(vehicle_id: str):
    """
    Return Facebook vehicle + AutoTrader matches, then set analysed_complete=true.
    Requires ai_last_updated set and completed_comparisons=true.
    """
    vehicle = get_by_id(vehicle_id)
    require_ready_for_analysis(vehicle)
    matches = list_by_fb_vehicle_id(vehicle_id)
    vehicle = mark_analysed_complete(vehicle_id)
    return {
        "message": "analysis complete",
        "vehicle": vehicle,
        "autotrader_matches": matches,
        "fb_vehicle_id": vehicle_id,
    }


@router.get("/{vehicle_id}")
def get_fb_vehicle(vehicle_id: str):
    """Single Facebook listing by id, including saved AutoTrader matches."""
    vehicle = get_by_id(vehicle_id)
    return {
        "vehicle": vehicle,
        "autotrader_matches": list_by_fb_vehicle_id(vehicle_id),
    }
