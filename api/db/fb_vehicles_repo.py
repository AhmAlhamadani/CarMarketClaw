from datetime import datetime, timedelta, UTC

from fastapi import HTTPException

from api.db.at_vehicles_repo import delete_by_fb_vehicle_id
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


def list_pending_completion_ids() -> list[str]:
    """Enriched (ai_last_updated set) but AutoTrader comparison not yet run."""
    response = (
        supabase.table("fb_vehicles")
        .select("id")
        .eq("completed_comparisons", False)
        .not_.is_("ai_last_updated", "null")
        .execute()
    )
    return [row["id"] for row in (response.data or []) if row.get("id")]


def list_pending_analysis_ids() -> list[str]:
    """Enriched + AutoTrader done, but full analysis not yet run."""
    response = (
        supabase.table("fb_vehicles")
        .select("id")
        .eq("analysed_complete", False)
        .eq("completed_comparisons", True)
        .not_.is_("ai_last_updated", "null")
        .execute()
    )
    return [row["id"] for row in (response.data or []) if row.get("id")]


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


def get_by_fb_id(fb_id: str) -> dict:
    response = (
        supabase.table("fb_vehicles")
        .select("*")
        .eq("fb_id", fb_id)
        .execute()
    )
    row = _first_row(response)
    if not row:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return row


def get_by_id_or_fb_id(ref: str) -> dict:
    """Look up a vehicle by Supabase uuid (id) or Facebook listing id (fb_id)."""
    try:
        return get_by_id(ref)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    return get_by_fb_id(ref)


def delete_older_than_days(days: int = 2) -> dict:
    """
    Delete fb_vehicles rows and their at_vehicles matches older than `days`
    (by created_at). Returns counts for logging.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    response = (
        supabase.table("fb_vehicles")
        .select("id")
        .lt("created_at", cutoff)
        .execute()
    )
    ids = [row["id"] for row in (response.data or []) if row.get("id")]
    if not ids:
        return {"deleted_vehicles": 0, "deleted_at_matches": 0, "cutoff": cutoff}

    at_response = (
        supabase.table("at_vehicles")
        .delete()
        .in_("fb_vehicle_id", ids)
        .execute()
    )
    at_count = len(at_response.data or [])

    supabase.table("fb_vehicles").delete().in_("id", ids).execute()

    return {
        "deleted_vehicles": len(ids),
        "deleted_at_matches": at_count,
        "cutoff": cutoff,
    }


def delete_by_id_or_fb_id(ref: str) -> dict:
    """Delete fb_vehicles row and related at_vehicles matches (uuid or fb_id)."""
    vehicle = get_by_id_or_fb_id(ref)
    vehicle_id = vehicle["id"]
    at_matches_deleted = delete_by_fb_vehicle_id(vehicle_id)

    supabase.table("fb_vehicles").delete().eq("id", vehicle_id).execute()

    try:
        get_by_id(vehicle_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            return {
                "vehicle_id": vehicle_id,
                "fb_id": vehicle.get("fb_id"),
                "title": vehicle.get("title"),
                "at_matches_deleted": at_matches_deleted,
            }
        raise

    raise HTTPException(status_code=500, detail="Vehicle delete failed")


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
