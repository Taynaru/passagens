"""Estruturas de dados compartilhadas e geração das datas a pesquisar."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


# Códigos das companhias -> nome amigável (foco nas que voam no Brasil)
AIRLINES = {
    "LA": "Latam", "JJ": "Latam", "G3": "Gol", "AD": "Azul", "2Z": "Azul",
    "AV": "Avianca", "O6": "Avianca", "TP": "TAP", "AA": "American",
    "UX": "Air Europa", "CM": "Copa", "AR": "Aerolíneas", "AF": "Air France",
}


def airline_name(code: str | None) -> str:
    """Devolve o nome da companhia a partir do código (ex.: 'LA' -> 'Latam')."""
    if not code:
        return "?"
    return AIRLINES.get(code.strip().upper(), code)


@dataclass
class Offer:
    """Uma oferta de voo ida-e-volta (em dinheiro ou em milhas)."""
    provider: str                 # "amadeus", "smiles", "sample"
    fare_type: str                # "cash" ou "miles"
    origin: str
    destination: str
    depart_date: str              # YYYY-MM-DD
    return_date: str              # YYYY-MM-DD
    price: float                  # total em R$ (dinheiro) ou taxas+embarque (milhas)
    miles: Optional[int] = None   # total de milhas ida+volta (só p/ fare_type="miles")
    currency: str = "BRL"
    airline: str = ""
    stops_out: int = 0
    stops_back: int = 0
    raw: dict = field(default_factory=dict)

    @property
    def trip_nights(self) -> int:
        d = date.fromisoformat(self.depart_date)
        r = date.fromisoformat(self.return_date)
        return (r - d).days

    def human(self) -> str:
        base = (f"{self.origin}->{self.destination} "
                f"{self.depart_date} / {self.return_date} "
                f"({self.trip_nights} noites, {airline_name(self.airline)})")
        if self.fare_type == "miles":
            miles_str = f"{self.miles:,}".replace(",", ".")
            return f"{base}: {miles_str} milhas + R$ {self.price:,.2f} de taxas"
        return f"{base}: R$ {self.price:,.2f}"


def generate_date_pairs(start_days: int, end_days: int, step_days: int,
                        trip_nights: list[int], max_pairs: int | None = None,
                        today: date | None = None) -> list[tuple[str, str]]:
    """Gera pares (ida, volta) varrendo a janela de busca.

    - start_days/end_days: a partir de quantos dias a contar de hoje e até quando.
    - step_days: de quantos em quantos dias amostrar as datas de ida.
    - trip_nights: durações de viagem (em noites) a testar para cada ida.
    - max_pairs: limite de pares (protege a cota da API).
    """
    today = today or date.today()
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    d = start_days
    while d <= end_days:
        depart = today + timedelta(days=d)
        for nights in trip_nights:
            ret = depart + timedelta(days=nights)
            key = (depart.isoformat(), ret.isoformat())
            if key not in seen:
                seen.add(key)
                pairs.append(key)
        d += step_days
    if max_pairs and len(pairs) > max_pairs:
        pairs = pairs[:max_pairs]
    return pairs
