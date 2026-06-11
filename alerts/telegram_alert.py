"""Envio de alertas por Telegram (notificação instantânea no celular).

Como configurar (bem simples, sem 'senha de app'):
  1. No Telegram, procure por @BotFather e mande /newbot. Siga as perguntas;
     no fim ele te dá um "token" (uma sequência tipo 123456:ABC-DEF...).
  2. Abra o seu novo bot e mande qualquer mensagem pra ele (ex.: "oi").
  3. Rode:  python main.py telegram-setup --token SEU_TOKEN_AQUI
     O app descobre seu "chat id" sozinho e salva tudo no .env.
"""
from __future__ import annotations

import logging

import requests

from alerts.email_alert import _fmt_brl, _fmt_int
from config import Settings
from models import Offer, airline_name

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"


def _build_message(deals: list[Offer], origin: str, destination: str,
                   max_rows: int = 15) -> str:
    lines = [f"✈️ <b>Queda de preço!</b>",
             f"{origin} ⇄ {destination} (ida e volta)\n"]
    for o in deals[:max_rows]:
        if o.fare_type == "miles":
            valor = f"{_fmt_int(o.miles or 0)} milhas + {_fmt_brl(o.price)} taxas"
            icone = "✈️"
        else:
            valor = _fmt_brl(o.price)
            icone = "💵"
        lines.append(f"{icone} {o.depart_date} → {o.return_date} "
                     f"({o.trip_nights}n, {airline_name(o.airline)})\n   <b>{valor}</b>")
    extra = len(deals) - max_rows
    if extra > 0:
        lines.append(f"\n… e mais {extra} oferta(s) no relatório.")
    lines.append("\n<i>Confirme no site da companhia/Smiles antes de comprar.</i>")
    return "\n".join(lines)


def _send(token: str, chat_id: str, text: str) -> bool:
    try:
        resp = requests.post(
            API.format(token=token, method="sendMessage"),
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=30,
        )
        resp.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Falha ao enviar Telegram: %s", e)
        return False


def send_deal_telegram(settings: Settings, deals: list[Offer]) -> bool:
    if not deals:
        return False
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        log.warning("Telegram não configurado. Rode 'python main.py telegram-setup'.")
        return False
    text = _build_message(deals, settings.origin, settings.destination)
    ok = _send(settings.telegram_bot_token, settings.telegram_chat_id, text)
    if ok:
        log.info("Alerta enviado no Telegram (%d ofertas).", len(deals))
    return ok


def send_test_telegram(settings: Settings) -> bool:
    """Manda uma mensagem de teste CLARA (não é promoção) para validar o canal."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        log.warning("Telegram não configurado. Rode 'python main.py telegram-setup'.")
        return False
    nights = ", ".join(str(n) for n in settings.trip_nights)
    text = ("✅ <b>Teste do Monitor de Passagens</b>\n\n"
            f"Estou funcionando e de olho na rota "
            f"<b>{settings.origin} ⇄ {settings.destination}</b> (ida e volta).\n\n"
            f"🔍 <b>Configuração atual:</b>\n"
            f"💵 Alerta de preço: até <b>R$ {settings.cash_threshold:.0f}</b>\n"
            f"📅 Período buscado: de <b>{settings.start_days}</b> a <b>{settings.end_days}</b> dias a partir de hoje\n"
            f"🌙 Durações testadas: <b>{nights}</b> noites\n\n"
            "Vou te avisar aqui assim que o preço ficar baixo. 📲\n\n"
            "<i>Esta é só uma mensagem de teste — não é uma promoção.</i>")
    ok = _send(settings.telegram_bot_token, settings.telegram_chat_id, text)
    if ok:
        log.info("Mensagem de teste enviada no Telegram.")
    return ok


def fetch_chat_id(token: str) -> str | None:
    """Descobre o chat id a partir das mensagens recentes enviadas ao bot.

    Você precisa ter mandado pelo menos uma mensagem ao bot antes.
    """
    try:
        resp = requests.get(API.format(token=token, method="getUpdates"), timeout=30)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception as e:  # noqa: BLE001
        log.error("Não consegui falar com o Telegram: %s", e)
        return None
    for upd in reversed(updates):
        msg = upd.get("message") or upd.get("edited_message") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            return str(chat["id"])
    return None
