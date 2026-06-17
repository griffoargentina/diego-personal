"""
Quick smoke test — runs each scraper for ONE brand only to be fast.
No email sent. Prints what it found.
Run from the tv-monitor/ directory:
    python test_scrapers.py
"""

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

from scrapers import SCRAPER_MAP

# One brand, one size bracket — keeps the test quick
BRAND = "Samsung"
MIN_INCHES = 55
MAX_INCHES = 75

print(f"\n{'='*60}")
print(f"Smoke test: '{BRAND}' TVs between {MIN_INCHES}\" and {MAX_INCHES}\"")
print(f"{'='*60}\n")

total = 0
for site_key, scraper in SCRAPER_MAP.items():
    print(f"--- {site_key.upper()} ---")
    try:
        items = scraper([BRAND], MIN_INCHES, MAX_INCHES)
        if not items:
            print("  (no results)\n")
            continue
        for it in items[:5]:  # show max 5 per site
            cuotas_str = f"  {it['cuotas']} cuotas s/i" if it.get("cuotas") else ""
            print(f"  ${it['price']:>12,}  {cuotas_str:20s}  {it['name'][:70]}")
            print(f"             {it['url'][:80]}")
        total += len(items)
        print(f"  → {len(items)} product(s) found\n")
    except Exception as e:
        print(f"  ERROR: {e}\n")

print(f"{'='*60}")
print(f"Total products found across all sites: {total}")
