"""Provedor de preços em MILHAS (Smiles / GOL).

ATENÇÃO: esta é a parte instável. A Smiles não oferece API pública oficial;
este módulo usa o mesmo endpoint que o site smiles.com.br chama internamente.
Isso pode:
  - parar de funcionar quando a Smiles mudar o endpoint, o esquema ou a x-api-key;
  - exigir que você atualize SMILES_API_KEY / SMILES_BASE_URL no .env.

Como obter a x-api-key (quando precisar atualizar):
  1. Abra smiles.com.br no Chrome e faça uma busca de voos.
  2. F12 -> aba "Network" (Rede) -> filtre por "search".
  3. Clique na requisição para .../airlines/search e veja os "Request Headers".
  4. Copie o valor de "x-api-key" para o .env.

Se a coleta falhar, o app continua funcionando normalmente só com dinheiro
(Amadeus). Os erros são registrados, não derrubam o programa.
"""
from __future__ import annotations

import logging
import time
from datetime import date

import requests

from models import Offer, generate_date_pairs
from .base import Provider

log = logging.getLogger(__name__)


class SmilesProvider(Provider):
    name = "smiles"
    fare_type = "miles"

    def __init__(self, settings):
        super().__init__(settings)
        self._leg_cache: dict[tuple[str, str, str], tuple[int, float, str] | None] = {}

    def _headers(self) -> dict:
        return {
            "x-api-key": self.s.smiles_api_key,
            "region": "BRASIL",
            "channel": "Web",
            "Accept": "application/json",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0 Safari/537.36"),
        }

    def _search_leg(self, origin: str, dest: str, day: str) -> tuple[int, float, str] | None:
        """Menor (milhas, taxas, cia) de um trecho (só ida) numa data.

        Retorna None se não houver voo / der erro.
        """
        cache_key = (origin, dest, day)
        if cache_key in self._leg_cache:
            return self._leg_cache[cache_key]

        params = {
            "originAirportCode": origin,
            "destinationAirportCode": dest,
            "departureDate": day,
            "adults": self.s.adults,
            "children": 0,
            "infants": 0,
            "cabinType": "all",
            "tripType": "1",          # 1 = só ida (combinamos ida+volta manualmente)
            "forceCongener": "false",
            "r": "BR",
        }
        try:
            resp = requests.get(self.s.smiles_base_url, headers=self._headers(),
                                params=params, timeout=45)
            if resp.status_code in (401, 403):
                log.error("Smiles recusou (HTTP %s): x-api-key provavelmente expirada. "
                          "Atualize SMILES_API_KEY no .env.", resp.status_code)
                self._leg_cache[cache_key] = None
                return None
            resp.raise_for_status()
            result = self._parse_leg(resp.json())
        except Exception as e:  # noqa: BLE001
            log.error("Smiles falhou em %s->%s %s: %s", origin, dest, day, e)
            result = None
        self._leg_cache[cache_key] = result
        return result

    @staticmethod
    def _parse_leg(payload: dict) -> tuple[int, float, str] | None:
        """Extrai o menor número de milhas + taxas do JSON da Smiles.

        O esquema da Smiles muda de tempos em tempos; por isso a leitura é
        defensiva (procura as chaves usuais e ignora o que não reconhece).
        """
        segments = (payload.get("requestedFlightSegmentList")
                    or payload.get("segments") or [])
        best: tuple[int, float, str] | None = None
        for seg in segments:
            flights = seg.get("flightList") or seg.get("flights") or []
            for fl in flights:
                airline = ""
                airline_obj = fl.get("airline") or {}
                if isinstance(airline_obj, dict):
                    airline = airline_obj.get("code") or airline_obj.get("name") or ""
                fares = fl.get("fareList") or fl.get("fares") or []
                for fare in fares:
                    miles = fare.get("miles") or fare.get("milesPrice") or 0
                    money = (fare.get("money") or fare.get("airportTax")
                             or fare.get("amount") or 0)
                    try:
                        miles = int(miles)
                        money = float(money)
                    except (TypeError, ValueError):
                        continue
                    if miles <= 0:
                        continue
                    if best is None or miles < best[0]:
                        best = (miles, round(money, 2), airline)
        return best

    def search(self) -> list[Offer]:
        if not self.s.smiles_api_key:
            log.warning("Smiles sem SMILES_API_KEY — pulando milhas.")
            return []
        pairs = generate_date_pairs(
            self.s.start_days, self.s.end_days, self.s.step_days,
            self.s.trip_nights, self.s.max_pairs,
        )
        log.info("Smiles: consultando %d combinações de datas (milhas)...", len(pairs))
        offers: list[Offer] = []
        for i, (depart, ret) in enumerate(pairs, 1):
            out = self._search_leg(self.s.origin, self.s.destination, depart)
            back = self._search_leg(self.s.destination, self.s.origin, ret)
            time.sleep(0.4)  # gentil com o servidor
            if not out or not back:
                log.info("  [%d/%d] %s/%s sem milhas disponíveis", i, len(pairs),
                         depart, ret)
                continue
            total_miles = out[0] + back[0]
            total_fees = round(out[1] + back[1], 2)
            airline = out[2] or back[2] or "GOL"
            offer = Offer(
                provider=self.name,
                fare_type="miles",
                origin=self.s.origin,
                destination=self.s.destination,
                depart_date=depart,
                return_date=ret,
                price=total_fees,
                miles=total_miles,
                currency=self.s.currency,
                airline=airline,
                raw={"out": out, "back": back},
            )
            offers.append(offer)
            log.info("  [%d/%d] %s", i, len(pairs), offer.human())
        return offers
