from datetime import datetime, UTC

from fastapi import HTTPException

from api.db.supabase_client import supabase
from api.db.fb_vehicles_schema import (
    normalize_scraper_row,
    normalize_agent_row,
    missing_required_fields,
)


def _first_row(response) -> dict | None:
    data = response.data
    if not data:
        return None
    return data[0]


def list_pending_enrichment() -> list[dict]:
    response = (
        supabase.table("fb_vehicles")
        .select("*")
        .is_("ai_last_updated", "null")
        .execute()
    )
    return response.data or []


def list_pending_completion() -> list[dict]:
    response = (
        supabase.table("fb_vehicles")
        .select("*")
        .eq("completed_comparisons", False)
        .execute()
    )
    return response.data or []


def list_pending_analysis() -> list[dict]:
    """Enriched + AutoTrader done, but full analysis not yet run."""
    response = (
        supabase.table("fb_vehicles")
        .select("*")
        .eq("analysed_complete", False)
        .eq("completed_comparisons", True)
        .not_.is_("ai_last_updated", "null")
        .execute()
    )
    return response.data or []


def require_ready_for_analysis(vehicle: dict) -> None:
    if vehicle.get("ai_last_updated") is None:
        raise HTTPException(
            status_code=409,
            detail="Vehicle not enriched (ai_last_updated is null)",
        )
    if not vehicle.get("completed_comparisons"):
        raise HTTPException(
            status_code=409,
            detail="AutoTrader comparisons not complete (completed_comparisons is false)",
        )


def mark_analysed_complete(vehicle_id: str) -> dict:
    response = (
        supabase.table("fb_vehicles")
        .update({"analysed_complete": True})
        .eq("id", vehicle_id)
        .execute()
    )
    saved = _first_row(response)
    if saved:
        return saved
    return get_by_id(vehicle_id)


def mark_completed_comparisons(vehicle_id: str) -> dict:
    response = (
        supabase.table("fb_vehicles")
        .update({"completed_comparisons": True})
        .eq("id", vehicle_id)
        .execute()
    )
    saved = _first_row(response)
    if saved:
        return saved
    return get_by_id(vehicle_id)


def get_by_id(vehicle_id: str) -> dict:
    response = (
        supabase.table("fb_vehicles")
        .select("*")
        .eq("id", vehicle_id)
        .execute()
    )
    row = _first_row(response)
    if not row:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return row


def save_scraped_vehicle(raw: dict) -> dict:
    row = normalize_scraper_row(raw)
    missing = missing_required_fields(row)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={"message": "Missing required listing fields", "fields": missing},
        )

    if not row.get("fb_id"):
        raise HTTPException(status_code=422, detail="fb_id is required")

    response = (
        supabase.table("fb_vehicles")
        .upsert(row, on_conflict="fb_id")
        .execute()
    )
    saved = _first_row(response)
    if saved:
        return saved

    lookup = (
        supabase.table("fb_vehicles")
        .select("*")
        .eq("fb_id", row["fb_id"])
        .execute()
    )
    saved = _first_row(lookup)
    if not saved:
        raise HTTPException(status_code=500, detail="Vehicle saved but could not be loaded")
    return saved


def save_agent_result(
    vehicle_id: str,
    raw: dict,
    allowed_fields: frozenset,
    *,
    touch_ai_last_updated: bool = True,
) -> dict:
    updates = normalize_agent_row(raw, allowed_fields)
    if not updates:
        raise HTTPException(status_code=422, detail="Agent produced no fields to save")

    if touch_ai_last_updated:
        updates["ai_last_updated"] = datetime.now(UTC).isoformat()

    response = (
        supabase.table("fb_vehicles")
        .update(updates)
        .eq("id", vehicle_id)
        .execute()
    )
    saved = _first_row(response)
    if saved:
        return saved

    return get_by_id(vehicle_id)
