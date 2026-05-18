import asyncio
import queue
from typing import Any

from fastapi import WebSocket


class AtConversationBridge:
    """Thread-safe bridge between Selenium (sync) and FastAPI WebSocket (async)."""

    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop, fb_vehicle: dict):
        self.websocket = websocket
        self.loop = loop
        self.fb_vehicle = fb_vehicle
        self._answers: queue.Queue = queue.Queue()
        self._cancelled = False

    def deliver_answer(self, value: str | None) -> None:
        self._answers.put(value)

    def cancel(self) -> None:
        self._cancelled = True
        self._answers.put(None)

    def send_status(self, message: str) -> None:
        """Push a progress line to the client (safe from Selenium thread)."""
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send_json({"type": "status", "message": message}),
            self.loop,
        )
        future.result(timeout=30)

    def prompt_fn(
        self,
        *,
        step: str,
        title: str,
        prompt: str,
        options: list[str],
        allow_blank: bool = True,
        suggested: str | None = None,
    ) -> str | None:
        if self._cancelled:
            raise RuntimeError("AutoTrader search cancelled")

        payload: dict[str, Any] = {
            "type": "question",
            "step": step,
            "title": title,
            "prompt": prompt,
            "options": options,
            "allow_blank": allow_blank,
        }
        if suggested:
            payload["suggested"] = suggested

        send_future = asyncio.run_coroutine_threadsafe(
            self.websocket.send_json(payload),
            self.loop,
        )
        send_future.result(timeout=30)

        try:
            answer = self._answers.get(timeout=600)
        except queue.Empty as exc:
            raise TimeoutError(f"No answer received for step {step}") from exc

        if self._cancelled:
            raise RuntimeError("AutoTrader search cancelled")

        if answer is None or answer == "":
            return None
        return str(answer).strip()
