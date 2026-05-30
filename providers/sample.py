"""Provedor de DADOS DE EXEMPLO (simulados).

Serve para você ver o app funcionando de ponta a ponta (busca -> banco ->
relatório -> alerta) sem precisar de nenhuma chave de API. Os preços são
gerados de forma plausível, com quedas ocasionais para testar os alertas.

Use com a flag --sample ou com USE_SAMPLE_DATA=true no .env.
"""
from __future__ import annotations

import logging
import random

from models import Offer, generate_date_pairs
from .base import Provider

log = logging.getLogger(__name__)

_AIRLINES = ["G3", "AD", "LA"]  # GOL, Azul, Latam


class SampleProvider(Provider):
    name = "sample"

    def __init__(self, settings, fare_type: str = "cash"):
        super().__init__(settings)
        self.fare_type = fare_type

    def search(self) -> list[Offer]:
        pairs = generate_date_pairs(
            self.s.start_days, self.s.end_days, self.s.step_days,
            self.s.trip_nights, self.s.max_pairs,
        )
        rng = random.Random()
        offers: list[Offer] = []
        for depart, ret in pairs:
            airline = rng.choice(_AIRLINES)
            if self.fare_type == "miles":
                miles = rng.choice([14000, 16000, 18000, 22000, 28000, 35000])
                miles += rng.randint(-1500, 1500)
                fees = round(rng.uniform(80, 140), 2)
                offers.append(Offer(
                    provider=self.name, fare_type="miles",
                    origin=self.s.origin, destination=self.s.destination,
                    depart_date=depart, return_date=ret,
                    price=fees, miles=miles, currency=self.s.currency,
                    airline=airline,
                ))
            else:
                price = round(rng.uniform(520, 1300), 2)
                offers.append(Offer(
                    provider=self.name, fare_type="cash",
                    origin=self.s.origin, destination=self.s.destination,
                    depart_date=depart, return_date=ret,
                    price=price, currency=self.s.currency, airline=airline,
                    stops_out=rng.choice([0, 0, 1]), stops_back=rng.choice([0, 0, 1]),
                ))
        log.info("Sample (%s): geradas %d ofertas simuladas.", self.fare_type, len(offers))
        return offers
