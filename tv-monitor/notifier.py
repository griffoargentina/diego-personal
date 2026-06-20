"""Send notifications via ntfy.sh (push) and optionally Resend (email)."""

import logging
import os
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

RESEND_FROM = "Monitor de Precios <onboarding@resend.dev>"


def _build_html(alerts: list[dict], scanned: list[dict], now: str) -> str:
    if alerts:
        rows = ""
        for a in alerts:
            reasons = " · ".join(a["reasons"])
            cuotas_str = f"{a['cuotas']} cuotas s/i" if a.get("cuotas") else "—"
            rows += f"""
            <tr>
              <td style="padding:8px;border:1px solid #ddd">{a['site']}</td>
              <td style="padding:8px;border:1px solid #ddd"><a href="{a['url']}" style="color:#0066cc">{a['name']}</a></td>
              <td style="padding:8px;border:1px solid #ddd;text-align:right"><strong>${a['price']:,.0f}</strong></td>
              <td style="padding:8px;border:1px solid #ddd;text-align:center">{cuotas_str}</td>
              <td style="padding:8px;border:1px solid #ddd;font-size:12px;color:#555">{reasons}</td>
            </tr>"""
        alert_section = f"""
        <h2 style="color:#cc0000">Ofertas detectadas</h2>
        <table style="border-collapse:collapse;width:100%;font-size:13px">
          <thead style="background:#1a1a2e;color:white">
            <tr>
              <th style="padding:10px;text-align:left">Sitio</th>
              <th style="padding:10px;text-align:left">Producto</th>
              <th style="padding:10px;text-align:right">Precio</th>
              <th style="padding:10px;text-align:center">Cuotas</th>
              <th style="padding:10px;text-align:left">Motivo</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>"""
    else:
        alert_section = """
        <div style="background:#f0f4f0;border-left:4px solid #4caf50;padding:12px 16px;margin:16px 0">
          <strong style="color:#2e7d32">Sin novedades</strong> — Ningún producto cumplió los umbrales esta vez.
        </div>"""

    scan_rows = ""
    for s in scanned:
        scan_rows += f"""
        <tr>
          <td style="padding:6px 8px;border:1px solid #eee">{s['label']}</td>
          <td style="padding:6px 8px;border:1px solid #eee;color:#555">{', '.join(s['sites'])}</td>
          <td style="padding:6px 8px;border:1px solid #eee;text-align:right">${s['max_price']:,}</td>
          <td style="padding:6px 8px;border:1px solid #eee;text-align:center">{s['total_found']}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;font-size:14px;max-width:800px;margin:0 auto;padding:16px">
      <h2 style="color:#1a1a2e;border-bottom:2px solid #1a1a2e;padding-bottom:8px">Price Monitor · {now}</h2>
      {alert_section}
      <h3 style="color:#444;margin-top:24px;font-size:13px">Resumen del escaneo</h3>
      <table style="border-collapse:collapse;width:100%;font-size:12px">
        <thead style="background:#f5f5f5">
          <tr>
            <th style="padding:6px 8px;text-align:left;border:1px solid #eee">Producto</th>
            <th style="padding:6px 8px;text-align:left;border:1px solid #eee">Sitios</th>
            <th style="padding:6px 8px;text-align:right;border:1px solid #eee">Precio máx.</th>
            <th style="padding:6px 8px;text-align:center;border:1px solid #eee">Encontrados</th>
          </tr>
        </thead>
        <tbody>{scan_rows}</tbody>
      </table>
      <p style="color:#aaa;font-size:11px;margin-top:24px">griffoargentina/diego-personal</p>
    </body></html>"""


def send_ntfy(alerts: list[dict], scanned: list[dict]) -> None:
    """Push notification via ntfy.sh — no account or API key needed."""
    topic = os.environ.get("NTFY_TOPIC", "griffo-price-monitor")
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if alerts:
        title = f"🔥 {len(alerts)} oferta(s) detectada(s)"
        lines = [f"• {a['site']}: {a['name'][:50]} → ${a['price']:,}" for a in alerts[:5]]
        body = "\n".join(lines)
        priority = "high"
        tags = "moneybag"
    else:
        title = "Price Monitor — Sin novedades"
        total = sum(s["total_found"] for s in scanned)
        body = f"Se revisaron {len(scanned)} productos ({total} resultados). Todo dentro del precio. {now}"
        priority = "low"
        tags = "white_check_mark"

    resp = requests.post(
        f"https://ntfy.sh/{topic}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": priority,
            "Tags": tags,
        },
        timeout=10,
    )
    resp.raise_for_status()
    logger.info("ntfy.sh notification sent to topic '%s'", topic)


def send_email(recipient: str, alerts: list[dict], scanned: list[dict]) -> None:
    """Send via Resend. Optional — only runs if RESEND_API_KEY is set."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.info("RESEND_API_KEY not set — skipping email")
        return

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    subject = (
        f"[Price Monitor] {len(alerts)} oferta(s) — {now}"
        if alerts else f"[Price Monitor] Sin novedades — {now}"
    )
    html = _build_html(alerts, scanned, now)

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": RESEND_FROM, "to": [recipient], "subject": subject, "html": html},
        timeout=15,
    )
    if not resp.ok:
        logger.warning("Resend error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()
    logger.info("Email sent via Resend to %s — id: %s", recipient, resp.json().get("id"))


def send_report(recipient: str, alerts: list[dict], scanned: list[dict]) -> None:
    """Send ntfy push (always) + Resend email (if key available)."""
    send_ntfy(alerts, scanned)
    send_email(recipient, alerts, scanned)
