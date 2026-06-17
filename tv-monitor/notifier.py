"""Send alert emails via Gmail SMTP."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_alert(recipient: str, alerts: list[dict]) -> None:
    """
    alerts: list of dicts with keys:
      site, name, price, cuotas, url, reason (list of str)
    """
    gmail_user = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]

    subject = f"[TV Monitor] {len(alerts)} oferta(s) detectada(s)"

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
      <h2 style="color:#1a1a2e">📺 TV Monitor — Ofertas detectadas</h2>
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
        Generado automáticamente por TV Monitor · griffoargentina/diego-personal
      </p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipient, msg.as_string())

    logger.info("Alert email sent to %s (%d items)", recipient, len(alerts))
