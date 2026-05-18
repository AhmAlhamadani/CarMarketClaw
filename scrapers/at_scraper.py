import json

from scrapers.at_pipeline import run_pipeline


def run_at_scraper_cli():
    final_payload = run_pipeline()
    if not final_payload:
        return None

    print("\n" + "=" * 60)
    print("FINAL PIPELINE OUTPUT")
    print("=" * 60)
    print(json.dumps(final_payload, indent=2, ensure_ascii=False))
    input("\nPress Enter to close everything...")
    return final_payload


if __name__ == "__main__":
    run_at_scraper_cli()
