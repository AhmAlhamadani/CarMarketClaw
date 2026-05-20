import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from api.db.at_vehicles_repo import (
    AtVehiclesSaveError,
    list_by_fb_vehicle_id,
    replace_matches_for_fb_vehicle,
)
from api.db.fb_vehicles_repo import get_by_id, mark_completed_comparisons
from api.services.at_conversation import AtConversationBridge
from api.services.at_prompt_provider import AtPromptProvider, build_step_overrides
from scrapers.at_pipeline import run_pipeline

router = APIRouter()

_SKIP_TOKENS = frozenset({"", ".", "skip", "any"})
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


def _parse_client_input(raw: str) -> tuple[str, str | None]:
    """
    Returns (action, value) where action is 'answer' or 'cancel'.

    Plain text (wscat-friendly):
      Audi          -> answer Audi
      (empty Enter) -> skip (None)
      cancel        -> cancel search
    """
    text = raw.strip()
    if not text:
        return "answer", None

    if text[0] in "{[":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON message must be an object")
        msg_type = data.get("type")
        if msg_type == "cancel":
            return "cancel", None
        if msg_type == "answer":
            value = data.get("value")
            if value is not None and not isinstance(value, str):
                value = str(value)
            return "answer", value
        raise ValueError(f"Unknown message type: {msg_type!r}")

    if text.lower() == "cancel":
        return "cancel", None
    if text.lower() in _SKIP_TOKENS:
        return "answer", None
    return "answer", text


async def _read_client_messages(websocket: WebSocket, bridge: AtConversationBridge) -> None:
    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            break

        if "text" not in message:
            await _safe_send(websocket, {
                "type": "error",
                "message": "Send a text line (e.g. Audi) or JSON answer.",
            })
            continue

        try:
            action, value = _parse_client_input(message["text"])
        except ValueError as exc:
            await _safe_send(websocket, {"type": "error", "message": str(exc)})
            continue

        if action == "cancel":
            bridge.cancel()
            break
        bridge.deliver_answer(value)


async def _safe_send(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


async def _load_fb_vehicle(fb_vehicle_id: str) -> dict:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(get_by_id, fb_vehicle_id),
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

    Example:
      POST /autotrader/match/{id}?make=Audi&model=A3
      GET  /autotrader/match/{id}
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
    fb_vehicle_id: str,
    params: AutotraderMatchParams,
) -> dict[str, Any]:
    lock = await _lock_for_vehicle(fb_vehicle_id)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="AutoTrader match already running for this vehicle",
        )

    async with lock:
        fb_vehicle = await _load_fb_vehicle(fb_vehicle_id)

        if fb_vehicle.get("completed_comparisons") and not params.force:
            existing = await asyncio.to_thread(list_by_fb_vehicle_id, fb_vehicle_id)
            return {
                "status": "already_complete",
                "message": "completed_comparisons is already true; pass force=true to re-run",
                "fb_vehicle_id": fb_vehicle_id,
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
            fb_vehicle_id,
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


@router.websocket("/ws/{fb_vehicle_id}")
async def autotrader_match_ws(websocket: WebSocket, fb_vehicle_id: str):
    """
    Interactive AutoTrader search for the 3 closest listing matches.

    Client protocol:
      Server -> started / question (includes "display" text) / retry / matched / status / scraped / complete / error
      Client -> plain text filter answers (e.g. Audi), number (e.g. 2), or cancel
      Typos are fuzzy-matched; invalid answers re-prompt without disconnecting.
      Connection closes after complete.

    Prefer the REST endpoint for automation: GET/POST /autotrader/match/{fb_vehicle_id}
    """
    await websocket.accept()
    await websocket.send_json({
        "type": "status",
        "message": "Connected. Loading Facebook listing from database...",
    })

    try:
        fb_vehicle = await _load_fb_vehicle(fb_vehicle_id)
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "message": exc.detail})
        return

    loop = asyncio.get_running_loop()
    bridge = AtConversationBridge(websocket, loop, fb_vehicle)

    await websocket.send_json({
        "type": "started",
        "fb_vehicle_id": fb_vehicle_id,
        "fb_vehicle": {
            "id": fb_vehicle.get("id"),
            "title": fb_vehicle.get("title"),
            "make": fb_vehicle.get("make"),
            "model": fb_vehicle.get("model"),
            "year": fb_vehicle.get("year"),
            "mileage": fb_vehicle.get("mileage"),
            "transmission": fb_vehicle.get("transmission"),
        },
    })

    reader = asyncio.create_task(_read_client_messages(websocket, bridge))

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                _run_pipeline_sync,
                bridge.prompt_fn,
                fb_vehicle,
                bridge.send_status,
            ),
            timeout=_PIPELINE_TIMEOUT_SEC,
        )

        if not result.get("success"):
            await _safe_send(websocket, {
                "type": "error",
                "message": "Filter selection did not complete",
                "filters_used": result.get("filters_used", {}),
            })
            return

        scraped = result.get("scraped_cars") or []
        if not scraped:
            await _safe_send(websocket, {
                "type": "error",
                "message": "No listings found on AutoTrader for these filters",
                "filters_used": result.get("filters_used", {}),
            })
            return

        await _safe_send(websocket, {
            "type": "scraped",
            "message": f"Found {len(scraped)} listing(s). Saving to database...",
            "matches": scraped,
        })

        try:
            saved = await asyncio.to_thread(
                replace_matches_for_fb_vehicle,
                fb_vehicle_id,
                scraped,
            )
            await asyncio.to_thread(mark_completed_comparisons, fb_vehicle_id)
        except AtVehiclesSaveError as exc:
            await _safe_send(websocket, {
                "type": "error",
                "message": str(exc),
                "matches": scraped,
                "saved": False,
            })
            return

        if await _safe_send(websocket, {
            "type": "complete",
            "fb_vehicle_id": fb_vehicle_id,
            "filters_used": result.get("filters_used", {}),
            "matches": scraped,
            "saved": saved,
        }):
            try:
                await websocket.close(code=1000, reason="complete")
            except Exception:
                pass
    except WebSocketDisconnect:
        bridge.cancel()
    except asyncio.TimeoutError:
        await _safe_send(websocket, {
            "type": "error",
            "message": f"Pipeline timed out after {_PIPELINE_TIMEOUT_SEC}s",
        })
    except RuntimeError as exc:
        if "cancelled" in str(exc).lower():
            await _safe_send(websocket, {"type": "cancelled", "message": str(exc)})
        else:
            await _safe_send(websocket, {"type": "error", "message": str(exc)})
    except AtVehiclesSaveError as exc:
        await _safe_send(websocket, {"type": "error", "message": str(exc), "saved": False})
    except Exception as exc:
        await _safe_send(websocket, {"type": "error", "message": str(exc)})
    finally:
        reader.cancel()
        try:
            await reader
        except asyncio.CancelledError:
            pass
        except WebSocketDisconnect:
            pass


@router.get("/matches/{fb_vehicle_id}")
def get_saved_matches(fb_vehicle_id: str):
    """Return previously saved AutoTrader matches for a Facebook listing."""
    get_by_id(fb_vehicle_id)
    return {"fb_vehicle_id": fb_vehicle_id, "matches": list_by_fb_vehicle_id(fb_vehicle_id)}
