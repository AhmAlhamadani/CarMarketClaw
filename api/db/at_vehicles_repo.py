from fastapi import HTTPException

from api.db.supabase_client import supabase
from api.db.at_vehicles_schema import missing_required_fields, normalize_at_row


class AtVehiclesSaveError(Exception):
    """Raised when Supabase save fails (safe to use from asyncio.to_thread)."""


def _first_rows(response) -> list[dict]:
    return list(response.data or [])


def replace_matches_for_fb_vehicle(fb_vehicle_id: str, cars: list[dict]) -> list[dict]:
    """Persist matches. Raises AtVehiclesSaveError (not HTTPException) for thread callers."""
    if not cars:
        raise AtVehiclesSaveError("No AutoTrader matches to save")

    rows = []
    for car in cars:
        row = normalize_at_row(car, fb_vehicle_id)
        missing = missing_required_fields(row)
        if missing:
            raise AtVehiclesSaveError(
                f"Invalid match row, missing {missing}: {car.get('title')!r}"
            )
        rows.append(row)

    try:
        supabase.table("at_vehicles").delete().eq("fb_vehicle_id", fb_vehicle_id).execute()
        response = supabase.table("at_vehicles").insert(rows).execute()
    except Exception as exc:
        raise AtVehiclesSaveError(f"Supabase error: {exc}") from exc

    saved = _first_rows(response)
    if saved:
        return saved

    raise AtVehiclesSaveError("Insert succeeded but no rows returned from Supabase")


def replace_matches_for_fb_vehicle_api(fb_vehicle_id: str, cars: list[dict]) -> list[dict]:
    try:
        return replace_matches_for_fb_vehicle(fb_vehicle_id, cars)
    except AtVehiclesSaveError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def delete_by_fb_vehicle_id(fb_vehicle_id: str) -> int:
    response = (
        supabase.table("at_vehicles")
        .delete()
        .eq("fb_vehicle_id", fb_vehicle_id)
        .execute()
    )
    return len(response.data or [])


def list_by_fb_vehicle_id(fb_vehicle_id: str) -> list[dict]:
    response = (
        supabase.table("at_vehicles")
        .select("*")
        .eq("fb_vehicle_id", fb_vehicle_id)
        .order("created_at", desc=True)
        .execute()
    )
    return _first_rows(response)
