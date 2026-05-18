import asyncio
import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from api.db.at_vehicles_repo import (
    AtVehiclesSaveError,
    list_by_fb_vehicle_id,
    replace_matches_for_fb_vehicle,
)
from api.db.fb_vehicles_repo import get_by_id
from api.services.at_conversation import AtConversationBridge
from scrapers.at_pipeline import run_pipeline

router = APIRouter()

_SKIP_TOKENS = frozenset({"", ".", "skip", "any"})


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


@router.websocket("/ws/{fb_vehicle_id}")
async def autotrader_match_ws(websocket: WebSocket, fb_vehicle_id: str):
    """
    Interactive AutoTrader search for the 3 closest listing matches.

    Client protocol:
      Server -> started / question / status / scraped / complete / error
      Client -> plain text filter answers (e.g. Audi), or cancel
      Connection closes after complete.
    """
    await websocket.accept()
    await websocket.send_json({
        "type": "status",
        "message": "Connected. Loading Facebook listing from database...",
    })

    try:
        fb_vehicle = await asyncio.wait_for(
            asyncio.to_thread(get_by_id, fb_vehicle_id),
            timeout=15,
        )
    except asyncio.TimeoutError:
        await websocket.send_json({
            "type": "error",
            "message": "Database timed out. Check SUPABASE_URL/SUPABASE_KEY and that uvicorn loaded .env.",
        })
        return
    except HTTPException as exc:
        await websocket.send_json({"type": "error", "message": exc.detail})
        return
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
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
        result = await asyncio.to_thread(
            run_pipeline,
            bridge.prompt_fn,
            fb_vehicle,
            bridge.send_status,
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
