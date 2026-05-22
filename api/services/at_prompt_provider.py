"""Prompt provider for AutoTrader filter selection (REST API)."""

from __future__ import annotations

from dataclasses import dataclass, field

from scrapers.at_option_matching import format_options_hint, match_option_choice


def build_step_overrides(
    *,
    make: str | None = None,
    model: str | None = None,
    trim: str | None = None,
    gearbox: str | None = None,
    min_mileage: str | None = None,
    max_mileage: str | None = None,
    min_year: str | None = None,
    max_year: str | None = None,
) -> dict[str, str | None]:
    """Map API field names to scraper step ids."""
    return {
        k: v
        for k, v in {
            "make": make,
            "model": model,
            "trim": trim,
            "gearbox": gearbox,
            "mileage_min": min_mileage,
            "mileage_max": max_mileage,
            "year_min": min_year,
            "year_max": max_year,
        }.items()
        if v is not None
    }


@dataclass
class AtPromptProvider:
    """
    Supplies filter answers to the Selenium scraper via query parameters and FB listing hints.

    Resolution order per step:
      1. Explicit override for that step (must match an available option)
      2. Suggested value from the Facebook listing (when use_suggestions=True)
      3. Skip (None)
    """

    overrides: dict[str, str | None] = field(default_factory=dict)
    use_suggestions: bool = True
    status_log: list[str] = field(default_factory=list)

    def send_status(self, message: str) -> None:
        self.status_log.append(message)

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
        if step in self.overrides:
            raw = self.overrides[step]
            if raw is None or str(raw).strip() == "":
                return None
            matched = match_option_choice(str(raw).strip(), options)
            if not matched:
                hint = format_options_hint(options) if options else "(no options)"
                raise ValueError(
                    f"Invalid filter for step '{step}': {raw!r}. Available: {hint}"
                )
            return matched

        if self.use_suggestions and suggested:
            matched = match_option_choice(str(suggested).strip(), options)
            if matched:
                return matched

        if allow_blank:
            return None

        raise ValueError(f"No value provided for required step '{step}'")
