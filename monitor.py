"""Orquestração: busca os preços, salva no banco, decide o que é 'oferta boa'
e dispara o alerta por e-mail."""
from __future__ import annotations

import logging

from alerts.email_alert import send_deal_email
from alerts.telegram_alert import send_deal_telegram
from config import Settings
from db import Database
from models import Offer
from providers import build_providers

log = logging.getLogger(__name__)

# Uma "nova mínima" só vira alerta se for pelo menos isto mais barata que a
# última oferta já alertada para as mesmas datas (evita spam por centavos).
MIN_IMPROVEMENT = 0.03  # 3%


def _dispatch_alerts(settings: Settings, deals: list[Offer]) -> bool:
    """Envia o alerta por todos os canais configurados (Telegram e/ou e-mail).

    Retorna True se pelo menos um canal conseguiu enviar.
    """
    sent = False
    if settings.telegram_bot_token and settings.telegram_chat_id:
        sent = send_deal_telegram(settings, deals) or sent
    if settings.smtp_user and settings.smtp_pass and settings.email_to:
        sent = send_deal_email(settings, deals) or sent
    has_channel = ((settings.telegram_bot_token and settings.telegram_chat_id)
                   or (settings.smtp_user and settings.email_to))
    if not has_channel:
        log.warning("Nenhum canal de alerta configurado. Configure o Telegram "
                    "('python main.py telegram-setup') ou o e-mail no .env.")
    return sent


def _is_better(offer: Offer, reference: float | int | None) -> bool:
    """True se 'offer' é uma nova mínima (mais barata que a referência histórica).

    Sem referência (primeira coleta, banco vazio) NÃO é considerado nova mínima —
    senão a primeira execução dispararia alerta para tudo. Nesse caso só vale o
    limiar configurado.
    """
    if reference is None:
        return False
    value = offer.miles if offer.fare_type == "miles" else offer.price
    if value is None:
        return False
    return value < reference


def evaluate_deals(settings: Settings, db: Database, offers: list[Offer],
                   prev_min_cash: float | None,
                   prev_min_miles: int | None) -> list[Offer]:
    """Decide quais ofertas merecem alerta.

    Critérios:
      1. Abaixo do limiar configurado (CASH_THRESHOLD / MILES_THRESHOLD), OU
      2. Nova mínima dos últimos NEW_LOW_DAYS dias (se ALERT_ON_NEW_LOW).
    Depois aplica anti-spam (cooldown + melhora mínima).
    """
    candidates: list[Offer] = []
    for o in offers:
        if o.fare_type == "miles":
            if o.miles is None:
                continue
            below = o.miles <= settings.miles_threshold
            new_low = settings.alert_on_new_low and _is_better(o, prev_min_miles)
        else:
            below = o.price <= settings.cash_threshold
            new_low = settings.alert_on_new_low and _is_better(o, prev_min_cash)
        if below or new_low:
            candidates.append(o)

    # anti-spam: só avisa essas datas de novo se o preço ficar pelo menos
    # MIN_IMPROVEMENT mais barato que o último alerta já enviado para elas.
    # (Evita repetir o mesmo preço a cada ciclo quando ele roda sozinho 24h.)
    deals: list[Offer] = []
    for o in candidates:
        prev_alert = db.min_alerted(o.fare_type, o.depart_date, o.return_date,
                                    settings.new_low_days)
        cur_val = o.miles if o.fare_type == "miles" else o.price
        if (prev_alert is not None and cur_val is not None
                and cur_val >= prev_alert * (1 - MIN_IMPROVEMENT)):
            continue  # já avisei essas datas por um preço igual ou melhor
        deals.append(o)

    # melhores primeiro
    deals.sort(key=lambda x: (x.miles or 0) if x.fare_type == "miles" else x.price)
    return deals


def run_cycle(settings: Settings, db: Database, force_sample: bool = False,
              send_alerts: bool = True) -> tuple[list[Offer], list[Offer]]:
    """Executa um ciclo completo de monitoramento."""
    providers = build_providers(settings, force_sample=force_sample)
    if not providers:
        log.warning("Nenhum provedor ativo. Configure as chaves no .env "
                    "ou rode com --sample.")
        return [], []

    # mínimos históricos ANTES de salvar o ciclo atual (referência p/ 'nova mínima')
    prev_min_cash = db.min_cash(settings.new_low_days)
    prev_min_miles = db.min_miles(settings.new_low_days)

    all_offers: list[Offer] = []
    for p in providers:
        log.info("== Provedor: %s (%s) ==", p.name, p.fare_type)
        try:
            all_offers.extend(p.search())
        except Exception as e:  # noqa: BLE001
            log.error("Provedor %s falhou: %s", p.name, e)

    if not all_offers:
        log.info("Nenhuma oferta coletada neste ciclo.")
        return [], []

    db.save_offers(all_offers)
    log.info("Salvas %d ofertas no banco.", len(all_offers))

    deals = evaluate_deals(settings, db, all_offers, prev_min_cash, prev_min_miles)
    if deals:
        log.info("%d oferta(s) dispararam alerta:", len(deals))
        for d in deals:
            log.info("  ⭐ %s", d.human())
        if send_alerts:
            if _dispatch_alerts(settings, deals):
                for d in deals:
                    db.mark_alerted(d)
    else:
        log.info("Nenhuma oferta atingiu os limiares de alerta neste ciclo.")

    return all_offers, deals
