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
        .eq("completed", False)
        .execute()
    )
    return response.data or []


def mark_completed(vehicle_id: str) -> dict:
    response = (
        supabase.table("fb_vehicles")
        .update({"completed": True})
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
