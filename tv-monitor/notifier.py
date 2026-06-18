"""Send alert emails via Resend API."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

RESEND_FROM = "Monitor de Precios <onboarding@resend.dev>"


def send_alert(recipient: str, alerts: list[dict]) -> None:
    api_key = os.environ["RESEND_API_KEY"]
    subject = f"[Price Monitor] {len(alerts)} oferta(s) detectada(s)"

    html_rows = ""
    for a in alerts:
        reasons = " · ".join(a["reasons"])
        cuotas_str = f"{a['cuotas']} cuotas s/i" if a.get("cuotas") else "—"
        html_rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd">{a['site']}</td>
          <td style="padding:8px;border:1px solid #ddd"><a href="{a['url']}">{a['name']}</a></td>
          <td style="padding:8px;border:1px solid #ddd;text-align:right"><strong>${a['price']:,.0f}</strong></td>
          <td style="padding:8px;border:1px solid #ddd;text-align:center">{cuotas_str}</td>
          <td style="padding:8px;border:1px solid #ddd">{reasons}</td>
        </tr>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;font-size:14px">
      <h2 style="color:#1a1a2e">Price Monitor — Ofertas detectadas</h2>
      <table style="border-collapse:collapse;width:100%">
        <thead style="background:#1a1a2e;color:white">
          <tr>
            <th style="padding:10px;text-align:left">Sitio</th>
            <th style="padding:10px;text-align:left">Producto</th>
            <th style="padding:10px;text-align:right">Precio</th>
            <th style="padding:10px;text-align:center">Cuotas</th>
            <th style="padding:10px;text-align:left">Motivo</th>
          </tr>
        </thead>
        <tbody>{html_rows}</tbody>
      </table>
      <p style="color:#888;font-size:12px;margin-top:20px">
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
    logger.info("Alert sent via Resend to %s (%d items) — id: %s",
                recipient, len(alerts), response.json().get("id"))
