import asyncio
import difflib
import queue
from typing import Any

from fastapi import WebSocket

from scrapers.at_option_matching import format_options_hint, match_option_choice

_MAX_ATTEMPTS = 8


def _format_question_display(
    *,
    step: str,
    title: str,
    prompt: str,
    options: list[str],
    suggested: str | None,
) -> str:
    lines = [
        "",
        "═" * 52,
        title.strip(),
        "═" * 52,
        prompt.strip(),
        "",
    ]
    if suggested:
        lines.append(f"  ★ Suggested: {suggested}")
        lines.append("")
    if options:
        lines.append("  Options:")
        for i, opt in enumerate(options, 1):
            mark = " ★" if suggested and opt.lower() == suggested.lower() else ""
            lines.append(f"    {i:>2}. {opt}{mark}")
        lines.append("")
    lines.append("  → Type an option name or number, Enter to skip, or 'cancel'")
    lines.append("═" * 52)
    return "\n".join(lines)


def _format_retry_message(answer: str, options: list[str]) -> str:
    near = difflib.get_close_matches(answer, options, n=3, cutoff=0.35)
    lines = [
        f"  ✗ '{answer}' was not recognized.",
        "",
        "  Try again — pick one of:",
    ]
    if near:
        lines.append("  Did you mean: " + ", ".join(near) + "?")
    else:
        lines.append("  " + format_options_hint(options))
    return "\n".join(lines)


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

    def _send_json_sync(self, payload: dict[str, Any]) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self.websocket.send_json(payload),
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

        display = _format_question_display(
            step=step,
            title=title,
            prompt=prompt,
            options=options,
            suggested=suggested,
        )

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            if self._cancelled:
                raise RuntimeError("AutoTrader search cancelled")

            payload: dict[str, Any] = {
                "type": "question",
                "step": step,
                "title": title,
                "prompt": prompt,
                "display": display,
                "options": options,
                "allow_blank": allow_blank,
                "attempt": attempt,
            }
            if suggested:
                payload["suggested"] = suggested

            self._send_json_sync(payload)

            try:
                answer = self._answers.get(timeout=600)
            except queue.Empty as exc:
                raise TimeoutError(f"No answer received for step {step}") from exc

            if self._cancelled:
                raise RuntimeError("AutoTrader search cancelled")

            if answer is None or str(answer).strip() == "":
                if allow_blank:
                    return None
                self._send_json_sync({
                    "type": "retry",
                    "step": step,
                    "display": "  Please choose an option (or type a number), or enter 'cancel'.",
                    "options": options,
                })
                continue

            raw = str(answer).strip()
            matched = match_option_choice(raw, options)
            if matched:
                if matched != raw:
                    self._send_json_sync({
                        "type": "matched",
                        "step": step,
                        "message": f"Using '{matched}' (from '{raw}')",
                        "value": matched,
                    })
                return matched

            self._send_json_sync({
                "type": "retry",
                "step": step,
                "display": _format_retry_message(raw, options),
                "options": options,
                "attempt": attempt,
            })

        if suggested:
            fallback = match_option_choice(suggested, options)
            if fallback:
                self._send_json_sync({
                    "type": "matched",
                    "step": step,
                    "message": f"Using suggested '{fallback}' after repeated invalid answers",
                    "value": fallback,
                })
                return fallback

        if allow_blank:
            self._send_json_sync({
                "type": "status",
                "message": f"Skipping {step} after too many invalid answers.",
            })
            return None

        raise ValueError(f"Could not match an option for {step} after {_MAX_ATTEMPTS} tries")
