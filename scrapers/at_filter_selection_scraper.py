import re
import time
from typing import Callable

from scrapers.at_option_matching import format_options_hint, match_option_choice

# prompt_fn(step, title, prompt, options, allow_blank, suggested) -> str | None
PromptFn = Callable[..., str | None]


def _read_choice(
    prompt_fn: PromptFn | None,
    *,
    step: str,
    title: str,
    prompt: str,
    options: list[str],
    allow_blank: bool = True,
    suggested: str | None = None,
) -> str | None:
    if prompt_fn is not None:
        return prompt_fn(
            step=step,
            title=title,
            prompt=prompt,
            options=options,
            allow_blank=allow_blank,
            suggested=suggested,
        )

    print("\n" + "=" * 60)
    print(title.upper())
    print("=" * 60)
    for i, opt in enumerate(options, 1):
        print(f"  {i:>2}. {opt}")
    print("\n" + "-" * 60)
    if suggested:
        print(f"(Suggested from listing: {suggested})")

    while True:
        user_choice = input(
            f"\n{prompt} (name, number, or Enter to skip): "
        ).strip()
        if not user_choice:
            if allow_blank:
                print("--> Bypassing selection.")
                return None
            print("  Please enter a value or press Enter to skip.")
            continue
        matched = match_option_choice(user_choice, options)
        if matched:
            if matched != user_choice:
                print(f"--> Using '{matched}'")
            return matched
        print(f"  Not recognized. Examples: {format_options_hint(options)}")


def reject_cookies(sb):
    try:
        iframe_selector = "iframe[id^='sp_message_iframe']"
        sb.switch_to_frame(iframe_selector, timeout=10)
        reject_button = 'button[title="Reject All"]'
        sb.wait_for_element_visible(reject_button, timeout=10)
        sb.js_click(reject_button)
    except Exception:
        pass
    finally:
        sb.switch_to_default_content()


def open_filters(sb):
    try:
        filter_button = 'button[data-testid="search-filter-toggle"]'
        sb.wait_for_element_visible(filter_button, timeout=10)
        sb.js_click(filter_button)
    except Exception as e:
        print(f"Could not open filters: {e}")


def click_accordion(sb, testid_name):
    try:
        button_selector = f'button[data-testid="{testid_name}"]'
        sb.wait_for_element_visible(button_selector, timeout=10)
        sb.js_click(button_selector)
    except Exception as e:
        print(f"Failed to click accordion {testid_name}: {e}")


def build_dropdown_map(sb, selector, timeout=10):
    try:
        sb.wait_for_element_visible(selector, timeout=timeout)
        raw_options = sb.get_select_options(selector)

        mapping = {}
        for opt in raw_options:
            if opt != "Any":
                clean_name = re.sub(r"\s*\([\d,]+\)", "", opt).strip()
                mapping[clean_name] = opt
        return mapping
    except Exception:
        return {}


def ask_for_single_choice(
    sb,
    dropdown_selector,
    step_title,
    prompt_text,
    *,
    step_id: str,
    prompt_fn: PromptFn | None = None,
    suggested: str | None = None,
):
    options_map = build_dropdown_map(sb, dropdown_selector, timeout=5)

    if not options_map:
        print(f"\n--> No options available for {step_title}. Skipping this step.")
        return True, None

    options = list(options_map.keys())
    user_choice = _read_choice(
        prompt_fn,
        step=step_id,
        title=step_title,
        prompt=prompt_text,
        options=options,
        allow_blank=True,
        suggested=suggested,
    )
    if not user_choice:
        return True, None

    sb.select_option_by_text(dropdown_selector, options_map[user_choice])
    return True, user_choice


def ask_for_gearbox(sb, *, prompt_fn: PromptFn | None = None, suggested: str | None = None):
    options_map = {}
    auto_label = 'label[for="transmission-automatic-checkbox"]'
    manual_label = 'label[for="transmission-manual-checkbox"]'

    if sb.is_element_present(auto_label):
        options_map["Automatic"] = auto_label
    if sb.is_element_present(manual_label):
        options_map["Manual"] = manual_label

    if not options_map:
        print("\n--> No gearbox options available for this car. Skipping.")
        return True, None

    options = list(options_map.keys())
    user_choice = _read_choice(
        prompt_fn,
        step="gearbox",
        title="STEP 4: CHOOSE A GEARBOX",
        prompt="What Gearbox do you want?",
        options=options,
        allow_blank=True,
        suggested=suggested,
    )
    if not user_choice:
        print("--> Bypassing gearbox selection.")
        return True, None

    sb.js_click(options_map[user_choice])
    return True, user_choice


def ask_for_range(
    sb,
    min_selector,
    max_selector,
    step_title,
    *,
    step_id: str,
    prompt_fn: PromptFn | None = None,
    suggested_min: str | None = None,
    suggested_max: str | None = None,
):
    final_min = None
    final_max = None

    min_map = build_dropdown_map(sb, min_selector, timeout=5)
    if min_map:
        min_options = list(min_map.keys())
        min_choice = _read_choice(
            prompt_fn,
            step=f"{step_id}_min",
            title=f"{step_title} — minimum",
            prompt="Select 'From' value",
            options=min_options,
            allow_blank=True,
            suggested=suggested_min,
        )
        if min_choice:
            sb.select_option_by_text(min_selector, min_map[min_choice])
            final_min = min_choice
            sb.wait(1.5)

    max_map = build_dropdown_map(sb, max_selector, timeout=5)
    if max_map:
        max_options = list(max_map.keys())
        max_choice = _read_choice(
            prompt_fn,
            step=f"{step_id}_max",
            title=f"{step_title} — maximum",
            prompt="Select 'To' value",
            options=max_options,
            allow_blank=True,
            suggested=suggested_max,
        )
        if max_choice:
            sb.select_option_by_text(max_selector, max_map[max_choice])
            final_max = max_choice

    return True, final_min, final_max


def run_interactive_scraper(sb, prompt_fn: PromptFn | None = None, suggestions: dict | None = None):
    suggestions = suggestions or {}
    response = {"success": False, "filters": {}}

    final_make = None
    final_model = None
    final_trim = None
    final_gearbox = None
    min_miles = max_miles = min_year = max_year = None

    print("Running OpenClaw Filter Selection...")

    reject_cookies(sb)
    sb.wait(1)
    open_filters(sb)
    sb.wait(1)

    click_accordion(sb, "make_and_model-facet-group")
    sb.wait(1)

    _, final_make = ask_for_single_choice(
        sb,
        "select#make",
        "STEP 1: CHOOSE A MAKE",
        "What Make are you looking for?",
        step_id="make",
        prompt_fn=prompt_fn,
        suggested=suggestions.get("make"),
    )
    if final_make:
        sb.wait(1.5)
        _, final_model = ask_for_single_choice(
            sb,
            "select#model",
            f"STEP 2: CHOOSE A MODEL FOR {final_make}",
            "What Model are you looking for?",
            step_id="model",
            prompt_fn=prompt_fn,
            suggested=suggestions.get("model"),
        )
        if final_model:
            sb.wait(1.5)
            _, final_trim = ask_for_single_choice(
                sb,
                "select#aggregated_trim",
                f"STEP 3: CHOOSE A TRIM FOR {final_model}",
                "What Trim are you looking for?",
                step_id="trim",
                prompt_fn=prompt_fn,
            )

    sb.wait(1.5)
    click_accordion(sb, "gearbox-facet-group")
    sb.wait(1)

    _, final_gearbox = ask_for_gearbox(
        sb,
        prompt_fn=prompt_fn,
        suggested=suggestions.get("gearbox"),
    )

    sb.wait(1.5)
    click_accordion(sb, "mileage-facet-group")
    sb.wait(1)

    _, min_miles, max_miles = ask_for_range(
        sb,
        "select#min_mileage",
        "select#max_mileage",
        "STEP 5: SET MILEAGE RANGE",
        step_id="mileage",
        prompt_fn=prompt_fn,
        suggested_min=suggestions.get("min_mileage"),
        suggested_max=suggestions.get("max_mileage"),
    )

    sb.wait(1.5)
    click_accordion(sb, "year-facet-group")
    sb.wait(1)

    _, min_year, max_year = ask_for_range(
        sb,
        "select#min_year_manufactured",
        "select#max_year_manufactured",
        "STEP 6: SET YEAR RANGE",
        step_id="year",
        prompt_fn=prompt_fn,
        suggested_min=suggestions.get("min_year"),
        suggested_max=suggestions.get("max_year"),
    )

    print("\n" + "=" * 60)
    print("STEP 7: APPLYING SEARCH FILTERS")
    print("=" * 60)
    try:
        search_btn = 'button[data-testid="search-apply-button"]'
        sb.wait_for_element_visible(search_btn, timeout=10)
        sb.js_click(search_btn)
        print("--> Clicked 'Search' button. Waiting for results to load...")
        sb.wait(3)
    except Exception as e:
        print(f"--> Failed to click the Search button: {e}")

    print("\n✅ All selections complete!")
    print(
        f"Make: {final_make} | Model: {final_model} | Trim: {final_trim or 'Any'}"
    )
    print(f"Gearbox: {final_gearbox or 'Any'}")
    print(f"Mileage: {min_miles or 'Any'} to {max_miles or 'Any'}")
    print(f"Year: {min_year or 'Any'} to {max_year or 'Any'}")

    response["success"] = True
    response["filters"] = {
        "make": final_make,
        "model": final_model,
        "trim": final_trim,
        "gearbox": final_gearbox,
        "min_mileage": min_miles,
        "max_mileage": max_miles,
        "min_year": min_year,
        "max_year": max_year,
    }
    return response
