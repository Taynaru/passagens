"""Banco de dados SQLite: histórico de preços e controle de alertas enviados."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from models import Offer


SCHEMA = """
CREATE TABLE IF NOT EXISTS price_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at  TEXT NOT NULL,
    provider     TEXT NOT NULL,
    fare_type    TEXT NOT NULL,
    origin       TEXT,
    destination  TEXT,
    depart_date  TEXT,
    return_date  TEXT,
    trip_nights  INTEGER,
    price        REAL,
    miles        INTEGER,
    currency     TEXT,
    airline      TEXT,
    stops_out    INTEGER,
    stops_back   INTEGER,
    raw          TEXT
);
CREATE INDEX IF NOT EXISTS idx_ph_fare ON price_history(fare_type, captured_at);
CREATE INDEX IF NOT EXISTS idx_ph_dates ON price_history(fare_type, depart_date, return_date);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at      TEXT NOT NULL,
    fare_type    TEXT,
    provider     TEXT,
    depart_date  TEXT,
    return_date  TEXT,
    price        REAL,
    miles        INTEGER
);
CREATE INDEX IF NOT EXISTS idx_alerts ON alerts_sent(fare_type, depart_date, return_date, sent_at);
"""


class Database:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ---- gravação ----
    def save_offers(self, offers: list[Offer]) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        rows = [
            (now, o.provider, o.fare_type, o.origin, o.destination,
             o.depart_date, o.return_date, o.trip_nights, o.price, o.miles,
             o.currency, o.airline, o.stops_out, o.stops_back,
             json.dumps(o.raw, ensure_ascii=False))
            for o in offers
        ]
        self.conn.executemany(
            """INSERT INTO price_history
               (captured_at, provider, fare_type, origin, destination,
                depart_date, return_date, trip_nights, price, miles,
                currency, airline, stops_out, stops_back, raw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        self.conn.commit()

    # ---- consultas de mínimos (referência histórica) ----
    def min_cash(self, days: int, depart: str | None = None,
                 ret: str | None = None) -> Optional[float]:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        q = ("SELECT MIN(price) AS m FROM price_history "
             "WHERE fare_type='cash' AND price IS NOT NULL AND captured_at >= ?")
        args: list = [since]
        if depart and ret:
            q += " AND depart_date=? AND return_date=?"
            args += [depart, ret]
        row = self.conn.execute(q, args).fetchone()
        return row["m"] if row and row["m"] is not None else None

    def min_miles(self, days: int, depart: str | None = None,
                  ret: str | None = None) -> Optional[int]:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        q = ("SELECT MIN(miles) AS m FROM price_history "
             "WHERE fare_type='miles' AND miles IS NOT NULL AND captured_at >= ?")
        args: list = [since]
        if depart and ret:
            q += " AND depart_date=? AND return_date=?"
            args += [depart, ret]
        row = self.conn.execute(q, args).fetchone()
        return int(row["m"]) if row and row["m"] is not None else None

    # ---- controle de alertas ----
    def recently_alerted(self, fare_type: str, depart: str, ret: str,
                         cooldown_hours: int) -> Optional[sqlite3.Row]:
        since = (datetime.now() - timedelta(hours=cooldown_hours)).isoformat()
        return self.conn.execute(
            """SELECT * FROM alerts_sent
               WHERE fare_type=? AND depart_date=? AND return_date=? AND sent_at >= ?
               ORDER BY sent_at DESC LIMIT 1""",
            (fare_type, depart, ret, since),
        ).fetchone()

    def min_alerted(self, fare_type: str, depart: str, ret: str,
                    days: int) -> Optional[float]:
        """Menor valor já alertado para essas datas dentro da janela (ou None).

        Usado para não repetir o mesmo alerta: só avisamos de novo se o preço
        ficar mais barato que o último que já avisamos para essas datas.
        """
        since = (datetime.now() - timedelta(days=days)).isoformat()
        col = "MIN(miles)" if fare_type == "miles" else "MIN(price)"
        row = self.conn.execute(
            f"""SELECT {col} AS m FROM alerts_sent
                WHERE fare_type=? AND depart_date=? AND return_date=? AND sent_at >= ?""",
            (fare_type, depart, ret, since),
        ).fetchone()
        return row["m"] if row and row["m"] is not None else None

    def mark_alerted(self, o: Offer) -> None:
        self.conn.execute(
            """INSERT INTO alerts_sent
               (sent_at, fare_type, provider, depart_date, return_date, price, miles)
               VALUES (?,?,?,?,?,?,?)""",
            (datetime.now().isoformat(timespec="seconds"), o.fare_type, o.provider,
             o.depart_date, o.return_date, o.price, o.miles),
        )
        self.conn.commit()

    # ---- relatórios ----
    def best_current(self, fare_type: str, limit: int = 10) -> list[sqlite3.Row]:
        """Melhores ofertas da coleta mais recente desse tipo de tarifa."""
        last = self.conn.execute(
            "SELECT MAX(captured_at) AS c FROM price_history WHERE fare_type=?",
            (fare_type,),
        ).fetchone()
        if not last or not last["c"]:
            return []
        order = "miles ASC" if fare_type == "miles" else "price ASC"
        return self.conn.execute(
            f"""SELECT * FROM price_history
                WHERE fare_type=? AND captured_at=?
                ORDER BY {order} LIMIT ?""",
            (fare_type, last["c"], limit),
        ).fetchall()

    def history_points(self, fare_type: str, days: int = 90) -> list[sqlite3.Row]:
        """Melhor preço por dia de coleta (para acompanhar a tendência)."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        col = "MIN(miles)" if fare_type == "miles" else "MIN(price)"
        return self.conn.execute(
            f"""SELECT substr(captured_at,1,10) AS dia, {col} AS melhor
                FROM price_history
                WHERE fare_type=? AND captured_at >= ?
                GROUP BY dia ORDER BY dia""",
            (fare_type, since),
        ).fetchall()
