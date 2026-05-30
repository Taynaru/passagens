"""Provedor de preços em DINHEIRO via Amadeus Self-Service API.

Cadastre-se grátis em https://developers.amadeus.com, crie um app e copie a
API Key e a API Secret para o .env (AMADEUS_API_KEY / AMADEUS_API_SECRET).

Ambiente:
  - test  -> https://test.api.amadeus.com   (dados de teste, cota generosa)
  - production -> https://api.amadeus.com    (dados reais, cota mensal grátis menor)
"""
from __future__ import annotations

import logging
import time

import requests

from models import Offer, generate_date_pairs
from .base import Provider

log = logging.getLogger(__name__)


class AmadeusProvider(Provider):
    name = "amadeus"
    fare_type = "cash"

    def __init__(self, settings):
        super().__init__(settings)
        self.base = ("https://api.amadeus.com"
                     if settings.amadeus_env == "production"
                     else "https://test.api.amadeus.com")
        self._token: str | None = None
        self._token_exp: float = 0.0

    # ---- autenticação OAuth2 (client_credentials) ----
    def _auth(self) -> str:
        if self._token and time.time() < self._token_exp - 60:
            return self._token
        resp = requests.post(
            f"{self.base}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.s.amadeus_key,
                "client_secret": self.s.amadeus_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        j = resp.json()
        self._token = j["access_token"]
        self._token_exp = time.time() + j.get("expires_in", 1799)
        return self._token

    # ---- uma busca ida-e-volta ----
    def _search_pair(self, depart: str, ret: str) -> Offer | None:
        token = self._auth()
        params = {
            "originLocationCode": self.s.origin,
            "destinationLocationCode": self.s.destination,
            "departureDate": depart,
            "returnDate": ret,
            "adults": self.s.adults,
            "currencyCode": self.s.currency,
            "max": 5,
        }
        for attempt in range(3):
            resp = requests.get(
                f"{self.base}/v2/shopping/flight-offers",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=45,
            )
            if resp.status_code == 429:  # rate limit -> espera e tenta de novo
                wait = 2 ** attempt
                log.warning("Amadeus rate limit (429). Aguardando %ss...", wait)
                time.sleep(wait)
                continue
            if resp.status_code == 401:  # token expirou no meio do caminho
                self._token = None
                token = self._auth()
                continue
            resp.raise_for_status()
            data = resp.json().get("data", [])
            if not data:
                return None
            best = min(data, key=lambda o: float(o["price"]["grandTotal"]))
            return self._to_offer(best, depart, ret)
        return None

    def _to_offer(self, raw: dict, depart: str, ret: str) -> Offer:
        price = float(raw["price"]["grandTotal"])
        itineraries = raw.get("itineraries", [])
        stops_out = max(len(itineraries[0]["segments"]) - 1, 0) if itineraries else 0
        stops_back = (max(len(itineraries[1]["segments"]) - 1, 0)
                      if len(itineraries) > 1 else 0)
        airline = ""
        if raw.get("validatingAirlineCodes"):
            airline = raw["validatingAirlineCodes"][0]
        elif itineraries:
            airline = itineraries[0]["segments"][0].get("carrierCode", "")
        return Offer(
            provider=self.name,
            fare_type="cash",
            origin=self.s.origin,
            destination=self.s.destination,
            depart_date=depart,
            return_date=ret,
            price=round(price, 2),
            currency=raw["price"].get("currency", self.s.currency),
            airline=airline,
            stops_out=stops_out,
            stops_back=stops_back,
            raw={"price": raw["price"], "id": raw.get("id")},
        )

    # ---- varredura da janela inteira ----
    def search(self) -> list[Offer]:
        pairs = generate_date_pairs(
            self.s.start_days, self.s.end_days, self.s.step_days,
            self.s.trip_nights, self.s.max_pairs,
        )
        log.info("Amadeus: consultando %d combinações de datas...", len(pairs))
        offers: list[Offer] = []
        for i, (depart, ret) in enumerate(pairs, 1):
            try:
                offer = self._search_pair(depart, ret)
                if offer:
                    offers.append(offer)
                    log.info("  [%d/%d] %s", i, len(pairs), offer.human())
                else:
                    log.info("  [%d/%d] %s/%s sem ofertas", i, len(pairs), depart, ret)
            except requests.HTTPError as e:
                log.error("  [%d/%d] erro Amadeus %s/%s: %s", i, len(pairs),
                          depart, ret, e)
            except Exception as e:  # noqa: BLE001
                log.error("  [%d/%d] falha %s/%s: %s", i, len(pairs), depart, ret, e)
            time.sleep(0.25)  # respeita o limite de requisições por segundo
        return offers
