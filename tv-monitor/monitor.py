"""
Main entry point.
  python tv-monitor/monitor.py
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import ALERT_EMAIL, PRICE_HISTORY_FILE, TV_TARGETS
from notifier import send_alert
from scrapers import SCRAPER_MAP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

HISTORY_PATH = Path(__file__).parent.parent / PRICE_HISTORY_FILE


def load_history() -> dict:
    if HISTORY_PATH.exists():
        try:
            return json.loads(HISTORY_PATH.read_text())
        except Exception:
            pass
    return {}


def save_history(history: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def history_key(item: dict) -> str:
    return f"{item['site']}|{item['url']}"


def already_alerted(history: dict, item: dict, reasons: list[str]) -> bool:
    """Return True if we already sent this exact alert in the last run."""
    key = history_key(item)
    if key not in history:
        return False
    prev = history[key]
    same_price = prev.get("price") == item["price"]
    same_cuotas = prev.get("cuotas") == item.get("cuotas")
    same_reasons = set(prev.get("reasons", [])) == set(reasons)
    return same_price and same_cuotas and same_reasons


def run() -> None:
    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()

    all_alerts: list[dict] = []
    new_history: dict = {}

    for target in TV_TARGETS:
        logger.info(
            "Scanning %s — max $%s — brands: %s",
            target["size_label"],
            f"{target['max_price']:,}",
            ", ".join(target["brands"]),
        )

        for site_key, scraper in SCRAPER_MAP.items():
            logger.info("  Scraping %s …", site_key)
            try:
                items = scraper(
                    target["brands"],
                    target["min_inches"],
                    target["max_inches"],
                )
            except Exception as e:
                logger.error("  Scraper %s crashed: %s", site_key, e)
                continue

            logger.info("  → %d products found", len(items))

            for item in items:
                reasons = []
                if item["price"] <= target["max_price"]:
                    reasons.append(
                        f"precio ≤ ${target['max_price']:,} (actual: ${item['price']:,})"
                    )
                if item.get("cuotas") and item["cuotas"] >= target["alert_cuotas"]:
                    reasons.append(
                        f"{item['cuotas']} cuotas sin interés detectadas"
                    )

                if not reasons:
                    continue

                key = history_key(item)
                new_history[key] = {
                    "price": item["price"],
                    "cuotas": item.get("cuotas"),
                    "reasons": reasons,
                    "last_seen": now_iso,
                }

                if already_alerted(history, item, reasons):
                    logger.info(
                        "  Skipping (same alert already sent): %s @ $%s",
                        item["name"][:60],
                        item["price"],
                    )
                    continue

                all_alerts.append({**item, "reasons": reasons})
                logger.info(
                    "  ALERT: %s @ $%s [%s]",
                    item["name"][:60],
                    item["price"],
                    ", ".join(reasons),
                )

    # Merge: keep old history for items not seen this run (up to 7 days)
    for key, val in history.items():
        if key not in new_history:
            new_history[key] = val  # keep for dedup across runs
    save_history(new_history)

    if all_alerts:
        logger.info("Sending email with %d alerts to %s", len(all_alerts), ALERT_EMAIL)
        try:
            send_alert(ALERT_EMAIL, all_alerts)
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            sys.exit(1)
    else:
        logger.info("No new alerts this run.")


if __name__ == "__main__":
    run()
