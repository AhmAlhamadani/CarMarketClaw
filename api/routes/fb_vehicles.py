from fastapi import APIRouter

from api.db.at_vehicles_repo import list_by_fb_vehicle_id
from api.db.fb_vehicles_repo import (
    delete_by_id_or_fb_id,
    get_by_id,
    list_pending_analysis_ids,
    list_pending_completion_ids,
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
    """Count and uuids of enriched vehicles (ai_last_updated set) awaiting AutoTrader."""
    vehicle_ids = list_pending_completion_ids()
    return {"count": len(vehicle_ids), "vehicle_ids": vehicle_ids}


@router.get("/pending_analysis")
def get_pending_analysis():
    """Count and uuids of vehicles ready for full analysis."""
    vehicle_ids = list_pending_analysis_ids()
    return {"count": len(vehicle_ids), "vehicle_ids": vehicle_ids}


@router.get("/{vehicle_id}/details")
def get_vehicle_details(vehicle_id: str):
    """Return make, model, transmission, mileage, and year for a vehicle by uuid."""
    vehicle = get_by_id(vehicle_id)
    return {
        "vehicle_id": vehicle_id,
        "make": vehicle.get("make"),
        "model": vehicle.get("model"),
        "transmission": vehicle.get("transmission"),
        "mileage": vehicle.get("mileage"),
        "year": vehicle.get("year"),
    }


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


@router.delete("/{vehicle_ref}")
def delete_fb_vehicle(vehicle_ref: str):
    """
    Delete a Facebook listing and its AutoTrader matches.
    Accepts Supabase uuid (id) or Facebook listing id (fb_id).
    """
    deleted = delete_by_id_or_fb_id(vehicle_ref)
    return {"message": "vehicle deleted", **deleted}
