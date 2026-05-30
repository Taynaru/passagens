"""Interface comum dos provedores de preço."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from config import Settings
from models import Offer

log = logging.getLogger(__name__)


class Provider(ABC):
    name: str = "base"
    fare_type: str = "cash"

    def __init__(self, settings: Settings):
        self.s = settings

    @abstractmethod
    def search(self) -> list[Offer]:
        """Retorna a melhor oferta por par (ida, volta) da janela configurada."""
        raise NotImplementedError
