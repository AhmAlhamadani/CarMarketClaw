"""Fuzzy matching for AutoTrader filter answers (typos, aliases, numbers)."""

from __future__ import annotations

import difflib
import re


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def match_option_choice(user_input: str, options: list[str]) -> str | None:
    """
    Map free-text user input to one of the allowed option labels.
    Returns None if no reasonable match.
    """
    if not options:
        return None

    raw = (user_input or "").strip()
    if not raw:
        return None

    if raw in options:
        return raw

    by_lower = {o.lower(): o for o in options}
    if raw.lower() in by_lower:
        return by_lower[raw.lower()]

    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]

    norm_in = _normalize(raw)
    for opt in options:
        if _normalize(opt) == norm_in:
            return opt

    # Substring match (e.g. "auto" -> "Automatic") — require min length
    if len(norm_in) >= 3:
        for opt in options:
            norm_opt = _normalize(opt)
            if norm_in in norm_opt or norm_opt in norm_in:
                return opt

    # Gearbox / transmission shortcuts
    if norm_in in ("auto", "aut", "automatic", "autamatic", "automaic", "automat"):
        for opt in options:
            if "automatic" in opt.lower():
                return opt
    if norm_in in ("man", "manual", "mannual"):
        for opt in options:
            if "manual" in opt.lower():
                return opt

    close = difflib.get_close_matches(raw, options, n=1, cutoff=0.55)
    if close:
        return close[0]

    close_lower = difflib.get_close_matches(raw.lower(), list(by_lower.keys()), n=1, cutoff=0.55)
    if close_lower:
        return by_lower[close_lower[0]]

    return None


def format_options_hint(options: list[str], limit: int = 8) -> str:
    if not options:
        return "(no options)"
    shown = options[:limit]
    parts = ", ".join(shown)
    if len(options) > limit:
        parts += f", … (+{len(options) - limit} more)"
    return parts
