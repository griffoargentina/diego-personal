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

from config import ALERT_EMAIL, PRICE_HISTORY_FILE, TARGETS
from notifier import send_report
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
    key = history_key(item)
    if key not in history:
        return False
    prev = history[key]
    return (
        prev.get("price") == item["price"]
        and prev.get("cuotas") == item.get("cuotas")
        and set(prev.get("reasons", [])) == set(reasons)
    )


def run() -> None:
    history = load_history()
    now_iso = datetime.now(timezone.utc).isoformat()

    all_alerts: list[dict] = []
    scan_summary: list[dict] = []
    new_history: dict = {}

    for target in TARGETS:
        logger.info(
            "Scanning '%s' — max $%s — sites: %s",
            target["label"],
            f"{target['max_price']:,}",
            ", ".join(target["sites"]),
        )

        target_total = 0
        for site_key in target["sites"]:
            scraper = SCRAPER_MAP.get(site_key)
            if not scraper:
                logger.warning("  No scraper registered for '%s'", site_key)
                continue

            for query in target["queries"]:
                logger.info("  [%s] query: %r", site_key, query)
                try:
                    items = scraper(query, target["keywords"], target["size_range"])
                except Exception as e:
                    logger.error("  Scraper %s crashed: %s", site_key, e)
                    continue

                logger.info("  → %d products found", len(items))
                target_total += len(items)

                for item in items:
                    reasons = []
                    if item["price"] <= target["max_price"]:
                        reasons.append(
                            f"precio ≤ ${target['max_price']:,} (actual: ${item['price']:,})"
                        )
                    if item.get("cuotas") and item["cuotas"] >= target["alert_cuotas"]:
                        reasons.append(f"{item['cuotas']} cuotas sin interés detectadas")

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
                            "  Skipping (same alert): %s @ $%s",
                            item["name"][:60], item["price"],
                        )
                        continue

                    all_alerts.append({**item, "reasons": reasons})
                    logger.info(
                        "  ALERT: %s @ $%s [%s]",
                        item["name"][:60], item["price"], ", ".join(reasons),
                    )

        scan_summary.append({
            "label": target["label"],
            "sites": target["sites"],
            "max_price": target["max_price"],
            "total_found": target_total,
        })

    # Keep history for items not seen this run (dedup across runs)
    for key, val in history.items():
        if key not in new_history:
            new_history[key] = val
    save_history(new_history)

    dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

    if dry_run:
        logger.info("DRY RUN — %d alert(s), no email sent", len(all_alerts))
        for a in all_alerts:
            cuotas_str = f"  {a['cuotas']} cuotas s/i" if a.get("cuotas") else ""
            logger.info("  [%s] $%s%s — %s", a["site"], f"{a['price']:,}", cuotas_str, a["name"][:60])
    else:
        logger.info("Sending report to %s (%d alerts)", ALERT_EMAIL, len(all_alerts))
        try:
            send_report(ALERT_EMAIL, all_alerts, scan_summary)
        except Exception as e:
            logger.error("Failed to send email: %s", e)
            sys.exit(1)


if __name__ == "__main__":
    run()
