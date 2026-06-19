"""Send alert emails via Resend API."""

import logging
import os
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

RESEND_FROM = "Monitor de Precios <onboarding@resend.dev>"


def send_report(recipient: str, alerts: list[dict], scanned: list[dict]) -> None:
    """
    Always sends an email.
    - alerts: products that triggered an alert
    - scanned: summary of what was scanned [{label, sites, results}]
    """
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.error("RESEND_API_KEY not set — cannot send email")
        return

    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    has_alerts = bool(alerts)
    subject = (
        f"[Price Monitor] {len(alerts)} oferta(s) encontrada(s) — {now}"
        if has_alerts
        else f"[Price Monitor] Sin novedades — {now}"
    )

    # ── Alert rows ──────────────────────────────────────────────────────────
    alert_section = ""
    if has_alerts:
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
        <h2 style="color:#cc0000;margin-top:24px">Ofertas detectadas</h2>
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
        <div style="background:#f0f4f0;border-left:4px solid #4caf50;padding:12px 16px;margin:16px 0;border-radius:4px">
          <strong style="color:#2e7d32">Sin novedades</strong> — Ningún producto cumplió los umbrales de precio esta vez.
        </div>"""

    # ── Scanned summary ─────────────────────────────────────────────────────
    scan_rows = ""
    for s in scanned:
        scan_rows += f"""
        <tr>
          <td style="padding:6px 8px;border:1px solid #eee">{s['label']}</td>
          <td style="padding:6px 8px;border:1px solid #eee;color:#555">{', '.join(s['sites'])}</td>
          <td style="padding:6px 8px;border:1px solid #eee;text-align:right">${s['max_price']:,}</td>
          <td style="padding:6px 8px;border:1px solid #eee;text-align:center">{s['total_found']}</td>
        </tr>"""

    scan_section = f"""
    <h3 style="color:#444;margin-top:24px;font-size:13px">Resumen del escaneo</h3>
    <table style="border-collapse:collapse;width:100%;font-size:12px;color:#333">
      <thead style="background:#f5f5f5">
        <tr>
          <th style="padding:6px 8px;text-align:left;border:1px solid #eee">Producto</th>
          <th style="padding:6px 8px;text-align:left;border:1px solid #eee">Sitios</th>
          <th style="padding:6px 8px;text-align:right;border:1px solid #eee">Precio máx.</th>
          <th style="padding:6px 8px;text-align:center;border:1px solid #eee">Encontrados</th>
        </tr>
      </thead>
      <tbody>{scan_rows}</tbody>
    </table>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;font-size:14px;max-width:800px;margin:0 auto;padding:16px">
      <h2 style="color:#1a1a2e;border-bottom:2px solid #1a1a2e;padding-bottom:8px">
        Price Monitor · {now}
      </h2>
      {alert_section}
      {scan_section}
      <p style="color:#aaa;font-size:11px;margin-top:24px">
        Generado automáticamente · griffoargentina/diego-personal
      </p>
    </body></html>"""

    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": RESEND_FROM, "to": [recipient], "subject": subject, "html": html},
        timeout=15,
    )
    response.raise_for_status()
    logger.info("Report sent via Resend to %s — id: %s",
                recipient, response.json().get("id"))
