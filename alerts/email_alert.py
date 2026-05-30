"""Envio de alertas por e-mail (SMTP)."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import Settings
from models import Offer, airline_name

log = logging.getLogger(__name__)


def _fmt_brl(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_int(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def _rows_html(deals: list[Offer]) -> str:
    rows = []
    for o in deals:
        if o.fare_type == "miles":
            valor = f"{_fmt_int(o.miles or 0)} milhas + {_fmt_brl(o.price)} taxas"
        else:
            valor = _fmt_brl(o.price)
        rows.append(
            f"<tr>"
            f"<td>{'✈️ Milhas' if o.fare_type == 'miles' else '💵 Dinheiro'}</td>"
            f"<td>{o.depart_date} → {o.return_date}</td>"
            f"<td style='text-align:center'>{o.trip_nights}</td>"
            f"<td>{airline_name(o.airline)}</td>"
            f"<td style='font-weight:bold;color:#0a7d2c'>{valor}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def build_email_html(deals: list[Offer], origin: str, destination: str,
                     max_rows: int = 15) -> str:
    extra = len(deals) - max_rows
    shown = deals[:max_rows]
    overflow = (f"<p style='color:#555'>… e mais {extra} oferta(s) no relatório.</p>"
                if extra > 0 else "")
    return f"""\
<html><body style="font-family:Arial,Helvetica,sans-serif;color:#222">
  <h2 style="color:#0a7d2c">✈️ Queda de preço encontrada!</h2>
  <p>Rota <b>{origin} ⇄ {destination}</b> (ida e volta). Ofertas que bateram seu alerta:</p>{overflow}
  <table cellpadding="8" cellspacing="0" border="0"
         style="border-collapse:collapse;width:100%;font-size:14px">
    <thead>
      <tr style="background:#0a7d2c;color:#fff;text-align:left">
        <th>Tipo</th><th>Datas (ida → volta)</th><th>Noites</th>
        <th>Cia</th><th>Valor</th>
      </tr>
    </thead>
    <tbody>
      {_rows_html(shown)}
    </tbody>
  </table>
  <p style="font-size:12px;color:#888;margin-top:20px">
    Alerta automático do Monitor de Passagens. Os valores mudam rápido —
    confirme no site da companhia/Smiles antes de comprar.
  </p>
</body></html>"""


def send_deal_email(settings: Settings, deals: list[Offer]) -> bool:
    """Envia o e-mail de alerta. Retorna True se enviou."""
    if not deals:
        return False
    if not (settings.smtp_user and settings.smtp_pass and settings.email_to):
        log.warning("E-mail não configurado (SMTP_USER/SMTP_PASS/EMAIL_TO). "
                    "Pulei o envio. Configure no .env.")
        return False

    cheapest = min(deals, key=lambda o: (o.miles or 0) if o.fare_type == "miles" else o.price)
    if cheapest.fare_type == "miles":
        resumo = f"{_fmt_int(cheapest.miles or 0)} milhas"
    else:
        resumo = _fmt_brl(cheapest.price)
    subject = f"✈️ {settings.origin}⇄{settings.destination}: oferta a partir de {resumo}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.email_from or settings.smtp_user
    msg["To"] = settings.email_to
    html = build_email_html(deals, settings.origin, settings.destination)
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if settings.smtp_tls:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(settings.smtp_user, settings.smtp_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                  context=ssl.create_default_context(), timeout=30) as s:
                s.login(settings.smtp_user, settings.smtp_pass)
                s.send_message(msg)
        log.info("E-mail de alerta enviado para %s (%d ofertas).",
                 settings.email_to, len(deals))
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Falha ao enviar e-mail: %s", e)
        return False


def send_test_email(settings: Settings) -> bool:
    """Manda um e-mail de teste para validar a configuração SMTP."""
    fake = Offer(
        provider="teste", fare_type="cash",
        origin=settings.origin, destination=settings.destination,
        depart_date="2026-07-01", return_date="2026-07-08",
        price=599.90, airline="G3",
    )
    return send_deal_email(settings, [fake])
