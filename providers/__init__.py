"""Fábrica de provedores conforme a configuração."""
from __future__ import annotations

import logging

from config import Settings
from .base import Provider
from .amadeus import AmadeusProvider
from .travelpayouts import TravelpayoutsProvider
from .smiles import SmilesProvider
from .sample import SampleProvider

log = logging.getLogger(__name__)


def build_providers(settings: Settings, force_sample: bool = False) -> list[Provider]:
    """Monta a lista de provedores ativos.

    - Dinheiro: Amadeus se houver chaves; senão avisa e ignora.
    - Milhas: Smiles se houver x-api-key; senão avisa e ignora.
    - force_sample (ou USE_SAMPLE_DATA): usa dados simulados para tudo.
    """
    if force_sample or settings.use_sample_data:
        providers: list[Provider] = []
        if settings.enable_cash:
            providers.append(SampleProvider(settings, "cash"))
        if settings.enable_miles:
            providers.append(SampleProvider(settings, "miles"))
        log.info("Modo DADOS DE EXEMPLO ativo (%d provedores simulados).", len(providers))
        return providers

    providers = []
    if settings.enable_cash:
        if settings.cash_provider == "amadeus":
            if settings.amadeus_key and settings.amadeus_secret:
                providers.append(AmadeusProvider(settings))
            else:
                log.warning("Dinheiro (Amadeus) sem chaves — pulando. "
                            "Preencha AMADEUS_API_KEY/SECRET ou rode com --sample.")
        else:  # travelpayouts (padrão)
            if settings.travelpayouts_token:
                providers.append(TravelpayoutsProvider(settings))
            else:
                log.warning("Dinheiro (Travelpayouts) sem token — pulando. "
                            "Rode 'python main.py travelpayouts-setup --token ...' "
                            "ou use --sample.")
    if settings.enable_miles:
        if settings.smiles_api_key:
            providers.append(SmilesProvider(settings))
        else:
            log.warning("Milhas ativadas mas sem SMILES_API_KEY — pulando. "
                        "Veja providers/smiles.py para obter a chave, ou rode com --sample.")
    return providers
