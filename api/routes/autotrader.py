import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.db.at_vehicles_repo import (
    AtVehiclesSaveError,
    list_by_fb_vehicle_id,
    replace_matches_for_fb_vehicle,
)
from api.db.fb_vehicles_repo import get_by_id_or_fb_id, mark_completed_comparisons
from api.services.at_prompt_provider import AtPromptProvider, build_step_overrides
from scrapers.at_pipeline import run_pipeline

router = APIRouter()

_PIPELINE_TIMEOUT_SEC = 900
_DB_TIMEOUT_SEC = 15

_vehicle_locks: dict[str, asyncio.Lock] = {}
_locks_guard = asyncio.Lock()


class AutotraderMatchParams(BaseModel):
    """Optional filter overrides. Omitted fields use FB listing hints or are skipped."""

    make: str | None = Field(default=None, description="AutoTrader make (e.g. Audi)")
    model: str | None = Field(default=None, description="Model for the selected make")
    trim: str | None = Field(default=None, description="Trim / aggregated trim")
    gearbox: str | None = Field(default=None, description="Automatic or Manual")
    min_mileage: str | None = Field(default=None, description="Min mileage (dropdown label)")
    max_mileage: str | None = Field(default=None, description="Max mileage (dropdown label)")
    min_year: str | None = Field(default=None, description="Min year manufactured")
    max_year: str | None = Field(default=None, description="Max year manufactured")
    use_suggestions: bool = Field(
        default=True,
        description="When a filter is not set, accept values inferred from the Facebook listing",
    )
    force: bool = Field(
        default=False,
        description="Run even if completed_comparisons is already true",
    )
    save: bool = Field(
        default=True,
        description="Persist top matches and set completed_comparisons=true",
    )


async def _lock_for_vehicle(fb_vehicle_id: str) -> asyncio.Lock:
    async with _locks_guard:
        if fb_vehicle_id not in _vehicle_locks:
            _vehicle_locks[fb_vehicle_id] = asyncio.Lock()
        return _vehicle_locks[fb_vehicle_id]


async def _load_fb_vehicle(ref: str) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(get_by_id_or_fb_id, ref),
            timeout=_DB_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="Database timed out. Check SUPABASE_URL/SUPABASE_KEY and .env.",
        ) from exc


def _run_pipeline_sync(
    prompt_fn,
    fb_vehicle: dict,
    status_fn,
) -> dict:
    return run_pipeline(prompt_fn, fb_vehicle, status_fn)


async def _execute_autotrader_match(
    fb_vehicle_id: str,
    fb_vehicle: dict,
    *,
    prompt_fn,
    status_fn,
    save: bool,
) -> dict[str, Any]:
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_pipeline_sync, prompt_fn, fb_vehicle, status_fn),
            timeout=_PIPELINE_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"AutoTrader pipeline timed out after {_PIPELINE_TIMEOUT_SEC}s",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not result.get("success"):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Filter selection did not complete",
                "filters_used": result.get("filters_used", {}),
            },
        )

    scraped = result.get("scraped_cars") or []
    if not scraped:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "No listings found on AutoTrader for these filters",
                "filters_used": result.get("filters_used", {}),
            },
        )

    saved: list[dict] | None = None
    if save:
        try:
            saved = await asyncio.to_thread(
                replace_matches_for_fb_vehicle,
                fb_vehicle_id,
                scraped,
            )
            await asyncio.to_thread(mark_completed_comparisons, fb_vehicle_id)
        except AtVehiclesSaveError as exc:
            raise HTTPException(
                status_code=500,
                detail={"message": str(exc), "matches": scraped, "saved": False},
            ) from exc

    return {
        "status": "complete",
        "fb_vehicle_id": fb_vehicle_id,
        "filters_used": result.get("filters_used", {}),
        "filters_stopped_early": result.get("filters_stopped_early", False),
        "search_result_count": result.get("search_result_count"),
        "matches": scraped,
        "saved": saved if save else False,
    }


@router.api_route("/match/{fb_vehicle_id}", methods=["GET", "POST"])
async def autotrader_match(
    fb_vehicle_id: str,
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    trim: str | None = Query(default=None),
    gearbox: str | None = Query(default=None),
    min_mileage: str | None = Query(default=None),
    max_mileage: str | None = Query(default=None),
    min_year: str | None = Query(default=None),
    max_year: str | None = Query(default=None),
    use_suggestions: bool = Query(default=True),
    force: bool = Query(default=False),
    save: bool = Query(default=True),
):
    """
    Run AutoTrader filter selection and scrape the top 3 closest listings.

    All filter query parameters are optional. Unset filters use values inferred
    from the Facebook listing when use_suggestions=true, otherwise they are skipped.

    Path accepts Supabase uuid (id) or Facebook listing id (fb_id).

    Example:
      POST /autotrader/match/{id}?make=Audi&model=A3
      GET  /autotrader/match/{fb_id}
    """
    params = AutotraderMatchParams(
        make=make,
        model=model,
        trim=trim,
        gearbox=gearbox,
        min_mileage=min_mileage,
        max_mileage=max_mileage,
        min_year=min_year,
        max_year=max_year,
        use_suggestions=use_suggestions,
        force=force,
        save=save,
    )
    return await _autotrader_match_impl(fb_vehicle_id, params)


async def _autotrader_match_impl(
    vehicle_ref: str,
    params: AutotraderMatchParams,
) -> dict[str, Any]:
    fb_vehicle = await _load_fb_vehicle(vehicle_ref)
    vehicle_id = fb_vehicle["id"]

    lock = await _lock_for_vehicle(vehicle_id)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="AutoTrader match already running for this vehicle",
        )

    async with lock:
        if fb_vehicle.get("completed_comparisons") and not params.force:
            existing = await asyncio.to_thread(list_by_fb_vehicle_id, vehicle_id)
            return {
                "status": "already_complete",
                "message": "completed_comparisons is already true; pass force=true to re-run",
                "fb_vehicle_id": vehicle_id,
                "matches": existing,
                "saved": False,
            }

        provider = AtPromptProvider(
            overrides=build_step_overrides(
                make=params.make,
                model=params.model,
                trim=params.trim,
                gearbox=params.gearbox,
                min_mileage=params.min_mileage,
                max_mileage=params.max_mileage,
                min_year=params.min_year,
                max_year=params.max_year,
            ),
            use_suggestions=params.use_suggestions,
        )

        payload = await _execute_autotrader_match(
            vehicle_id,
            fb_vehicle,
            prompt_fn=provider.prompt_fn,
            status_fn=provider.send_status,
            save=params.save,
        )
        payload["status_log"] = provider.status_log
        payload["fb_vehicle"] = {
            "id": fb_vehicle.get("id"),
            "title": fb_vehicle.get("title"),
            "make": fb_vehicle.get("make"),
            "model": fb_vehicle.get("model"),
            "year": fb_vehicle.get("year"),
            "mileage": fb_vehicle.get("mileage"),
            "transmission": fb_vehicle.get("transmission"),
        }
        return payload
