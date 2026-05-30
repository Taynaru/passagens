"""Provedor de preços em DINHEIRO via Travelpayouts (dados Aviasales).

Fonte gratuita e sustentável (substitui a Amadeus, que será desligada em 2026).
Usa o endpoint v3 "prices_for_dates", que devolve as passagens mais baratas
encontradas por usuários nos últimos dias — ótimo para "sem data fixa", pois
varre meses inteiros de uma vez (poucas chamadas).

Como obter o token (grátis):
  1. Crie conta em https://www.travelpayouts.com (pode traduzir a página).
  2. No painel, vá em Ferramentas/Tools -> API -> "Token de acesso" (Data API).
  3. Rode:  python main.py travelpayouts-setup --token SEU_TOKEN

Observação honesta: os preços são "cacheados" (do que outros usuários acharam
recentemente), então podem estar levemente atrasados. Servem muito bem para
detectar tendências e quedas; sempre confirme no site da companhia antes de comprar.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import requests

from models import Offer
from .base import Provider

log = logging.getLogger(__name__)

ENDPOINT = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def _months_in_window(start_days: int, end_days: int,
                      today: date | None = None) -> list[str]:
    today = today or date.today()
    start = today + timedelta(days=start_days)
    end = today + timedelta(days=end_days)
    months: list[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


def _next_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    m += 1
    if m > 12:
        m, y = 1, y + 1
    return f"{y:04d}-{m:02d}"


class TravelpayoutsProvider(Provider):
    name = "travelpayouts"
    fare_type = "cash"

    def __init__(self, settings):
        super().__init__(settings)
        # Como ela é flexível nas datas, aceitamos uma faixa ampla de duração
        # de viagem (em noites), para não perder ofertas baratas de outros tamanhos.
        self.min_nights = max(1, min(settings.trip_nights) - 2)   # ex.: 2
        self.max_nights = max(settings.trip_nights) + 11          # ex.: 21

    def _query(self, departure_month: str, return_month: str) -> list[dict]:
        params = {
            "origin": self.s.origin,
            "destination": self.s.destination,
            "departure_at": departure_month,
            "return_at": return_month,
            "currency": self.s.currency.lower(),
            "unique": "false",
            "sorting": "price",
            "direct": "false",
            "limit": 1000,
            "page": 1,
            "one_way": "false",
        }
        try:
            resp = requests.get(
                ENDPOINT, params=params,
                headers={"X-Access-Token": self.s.travelpayouts_token},
                timeout=45,
            )
            if resp.status_code in (401, 403):
                log.error("Travelpayouts recusou (HTTP %s): token inválido? "
                          "Rode 'python main.py travelpayouts-setup --token ...'.",
                          resp.status_code)
                return []
            resp.raise_for_status()
            payload = resp.json()
            if not payload.get("success", True):
                log.error("Travelpayouts retornou erro: %s", payload)
                return []
            return payload.get("data", []) or []
        except Exception as e:  # noqa: BLE001
            log.error("Travelpayouts falhou (%s -> %s): %s",
                      departure_month, return_month, e)
            return []

    def _to_offer(self, row: dict) -> Offer | None:
        depart = (row.get("departure_at") or "")[:10]
        ret = (row.get("return_at") or "")[:10]
        price = row.get("price")
        if not depart or not ret or price is None:
            return None
        return Offer(
            provider=self.name,
            fare_type="cash",
            origin=self.s.origin,
            destination=self.s.destination,
            depart_date=depart,
            return_date=ret,
            price=round(float(price), 2),
            currency=self.s.currency,
            airline=row.get("airline", "") or "",
            stops_out=int(row.get("transfers", 0) or 0),
            stops_back=int(row.get("return_transfers", 0) or 0),
            raw={"link": row.get("link", "")},
        )

    def search(self) -> list[Offer]:
        if not self.s.travelpayouts_token:
            log.warning("Travelpayouts sem token — pulando preços em dinheiro.")
            return []

        today = date.today()
        win_start = today + timedelta(days=self.s.start_days)
        win_end = today + timedelta(days=self.s.end_days)
        months = _months_in_window(self.s.start_days, self.s.end_days, today)

        # para cada mês de ida, busca volta no mesmo mês e no seguinte
        # (cobre viagens que cruzam a virada do mês)
        best: dict[tuple[str, str], Offer] = {}
        for dm in months:
            for rm in (dm, _next_month(dm)):
                for row in self._query(dm, rm):
                    offer = self._to_offer(row)
                    if not offer:
                        continue
                    try:
                        d = date.fromisoformat(offer.depart_date)
                        r = date.fromisoformat(offer.return_date)
                    except ValueError:
                        continue
                    nights = (r - d).days
                    # filtra: dentro da janela e com duração de viagem razoável
                    if not (win_start <= d <= win_end):
                        continue
                    if not (self.min_nights <= nights <= self.max_nights):
                        continue
                    key = (offer.depart_date, offer.return_date)
                    if key not in best or offer.price < best[key].price:
                        best[key] = offer

        offers = sorted(best.values(), key=lambda o: o.price)
        log.info("Travelpayouts: %d ofertas (ida-e-volta) na janela.", len(offers))
        for o in offers[:10]:
            log.info("  %s", o.human())
        return offers
