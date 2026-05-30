"""Carrega as configurações a partir do arquivo .env (ou variáveis de ambiente)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(_get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _get_bool(name: str, default: bool) -> bool:
    v = _get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "sim", "y", "s")


def _get_list_int(name: str, default: list[int]) -> list[int]:
    raw = _get(name)
    if not raw:
        return default
    try:
        return [int(x) for x in raw.split(",") if x.strip()]
    except ValueError:
        return default


@dataclass
class Settings:
    # Rota
    origin: str
    destination: str
    adults: int
    currency: str

    # Janela de busca
    start_days: int
    end_days: int
    step_days: int
    trip_nights: list[int]
    max_pairs: int

    # Provedores
    enable_cash: bool
    enable_miles: bool
    use_sample_data: bool
    cash_provider: str            # "travelpayouts" ou "amadeus"

    # Travelpayouts (preços em dinheiro — fonte gratuita recomendada)
    travelpayouts_token: str

    # Amadeus (alternativa; portal self-service será desligado em jul/2026)
    amadeus_env: str
    amadeus_key: str
    amadeus_secret: str

    # Smiles (milhas)
    smiles_base_url: str
    smiles_api_key: str

    # Alertas / limiares
    cash_threshold: float
    miles_threshold: int
    alert_on_new_low: bool
    new_low_days: int
    alert_cooldown_hours: int

    # E-mail
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_tls: bool
    email_from: str
    email_to: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # Geral
    db_path: str
    report_path: str


def load_settings() -> Settings:
    # relê o .env a cada chamada (pega edições feitas em tempo de execução,
    # ex.: logo após o telegram-setup salvar o chat id)
    load_dotenv(BASE_DIR / ".env", override=True)
    return Settings(
        origin=_get("ORIGIN", "FOR"),
        destination=_get("DESTINATION", "CNF"),
        adults=_get_int("ADULTS", 1),
        currency=_get("CURRENCY", "BRL"),

        start_days=_get_int("START_DAYS", 21),
        end_days=_get_int("END_DAYS", 120),
        step_days=_get_int("STEP_DAYS", 7),
        trip_nights=_get_list_int("TRIP_NIGHTS", [4, 7, 10]),
        max_pairs=_get_int("MAX_PAIRS", 40),

        enable_cash=_get_bool("ENABLE_CASH", True),
        enable_miles=_get_bool("ENABLE_MILES", True),
        use_sample_data=_get_bool("USE_SAMPLE_DATA", False),
        cash_provider=_get("CASH_PROVIDER", "travelpayouts").lower(),

        travelpayouts_token=_get("TRAVELPAYOUTS_TOKEN", ""),

        amadeus_env=_get("AMADEUS_ENV", "test"),
        amadeus_key=_get("AMADEUS_API_KEY", ""),
        amadeus_secret=_get("AMADEUS_API_SECRET", ""),

        smiles_base_url=_get("SMILES_BASE_URL",
                             "https://api-air-flightsearch-prd.smiles.com.br/v1/airlines/search"),
        smiles_api_key=_get("SMILES_API_KEY", ""),

        cash_threshold=_get_float("CASH_THRESHOLD", 700.0),
        miles_threshold=_get_int("MILES_THRESHOLD", 20000),
        alert_on_new_low=_get_bool("ALERT_ON_NEW_LOW", True),
        new_low_days=_get_int("NEW_LOW_DAYS", 30),
        alert_cooldown_hours=_get_int("ALERT_COOLDOWN_HOURS", 12),

        smtp_host=_get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=_get_int("SMTP_PORT", 587),
        smtp_user=_get("SMTP_USER", ""),
        smtp_pass=_get("SMTP_PASS", ""),
        smtp_tls=_get_bool("SMTP_TLS", True),
        email_from=_get("EMAIL_FROM", _get("SMTP_USER", "")),
        email_to=_get("EMAIL_TO", ""),

        telegram_bot_token=_get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=_get("TELEGRAM_CHAT_ID", ""),

        db_path=_get("DB_PATH", str(BASE_DIR / "data" / "precos.db")),
        report_path=_get("REPORT_PATH", str(BASE_DIR / "data" / "relatorio.html")),
    )


def set_env_value(key: str, value: str) -> None:
    """Atualiza (ou adiciona) uma chave no arquivo .env, preservando o resto."""
    path = BASE_DIR / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
