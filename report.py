"""Gera um relatório (texto no terminal + HTML) com os melhores preços atuais
e a tendência recente."""
from __future__ import annotations

from datetime import datetime

from config import Settings
from db import Database
from models import airline_name


def _fmt_brl(v) -> str:
    if v is None:
        return "-"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_int(v) -> str:
    if v is None:
        return "-"
    return f"{int(v):,}".replace(",", ".")


def print_report(settings: Settings, db: Database) -> None:
    print(f"\n=== Monitor de Passagens  {settings.origin} <-> {settings.destination} ===")
    print(f"Gerado em {datetime.now():%d/%m/%Y %H:%M}\n")

    cash = db.best_current("cash", limit=10)
    print("-- 💵 MELHORES EM DINHEIRO (coleta mais recente) --")
    if cash:
        for r in cash:
            print(f"  {r['depart_date']} -> {r['return_date']} "
                  f"({r['trip_nights']}n, {airline_name(r['airline'])}): {_fmt_brl(r['price'])}")
    else:
        print("  (sem dados ainda — rode 'run')")

    miles = db.best_current("miles", limit=10)
    print("\n-- ✈️  MELHORES EM MILHAS (coleta mais recente) --")
    if miles:
        for r in miles:
            print(f"  {r['depart_date']} -> {r['return_date']} "
                  f"({r['trip_nights']}n, {airline_name(r['airline'])}): "
                  f"{_fmt_int(r['miles'])} milhas + {_fmt_brl(r['price'])} taxas")
    else:
        print("  (sem dados ainda)")

    print(f"\nMínima dinheiro ({settings.new_low_days}d): "
          f"{_fmt_brl(db.min_cash(settings.new_low_days))}")
    print(f"Mínima milhas   ({settings.new_low_days}d): "
          f"{_fmt_int(db.min_miles(settings.new_low_days))} milhas")
    print(f"Limiar de alerta: {_fmt_brl(settings.cash_threshold)} / "
          f"{_fmt_int(settings.miles_threshold)} milhas\n")


def _table_html(rows, fare_type) -> str:
    if not rows:
        return "<p style='color:#888'>Sem dados ainda.</p>"
    out = ["<table cellpadding='6' style='border-collapse:collapse;width:100%;font-size:14px'>",
           "<tr style='background:#0a7d2c;color:#fff;text-align:left'>"
           "<th>Ida → Volta</th><th>Noites</th><th>Cia</th><th>Valor</th></tr>"]
    for r in rows:
        if fare_type == "miles":
            valor = f"{_fmt_int(r['miles'])} milhas + {_fmt_brl(r['price'])}"
        else:
            valor = _fmt_brl(r["price"])
        out.append(f"<tr style='border-bottom:1px solid #eee'>"
                   f"<td>{r['depart_date']} → {r['return_date']}</td>"
                   f"<td style='text-align:center'>{r['trip_nights']}</td>"
                   f"<td>{airline_name(r['airline'])}</td>"
                   f"<td style='font-weight:bold'>{valor}</td></tr>")
    out.append("</table>")
    return "\n".join(out)


def write_html_report(settings: Settings, db: Database) -> str:
    cash = db.best_current("cash", limit=15)
    miles = db.best_current("miles", limit=15)
    hist_cash = db.history_points("cash", days=90)
    hist_miles = db.history_points("miles", days=90)

    hist_rows = []
    for r in hist_cash:
        hist_rows.append(f"<tr><td>{r['dia']}</td><td>{_fmt_brl(r['melhor'])}</td><td>-</td></tr>")
    miles_by_day = {r["dia"]: r["melhor"] for r in hist_miles}
    # mescla milhas na tabela de tendência
    merged = {r["dia"]: [r["melhor"], None] for r in hist_cash}
    for dia, m in miles_by_day.items():
        merged.setdefault(dia, [None, None])[1] = m
    trend = "".join(
        f"<tr><td>{dia}</td><td>{_fmt_brl(v[0])}</td>"
        f"<td>{_fmt_int(v[1])+' milhas' if v[1] else '-'}</td></tr>"
        for dia, v in sorted(merged.items())
    )

    html = f"""<!DOCTYPE html><html lang="pt-br"><head><meta charset="utf-8">
<title>Monitor de Passagens {settings.origin}-{settings.destination}</title></head>
<body style="font-family:Arial,Helvetica,sans-serif;max-width:900px;margin:24px auto;color:#222">
  <h1 style="color:#0a7d2c">✈️ Monitor de Passagens — {settings.origin} ⇄ {settings.destination}</h1>
  <p>Atualizado em {datetime.now():%d/%m/%Y %H:%M}. Ida e volta, sem data fixa
     (varrendo {settings.start_days} a {settings.end_days} dias à frente).</p>
  <p><b>Mínima (dinheiro, {settings.new_low_days}d):</b> {_fmt_brl(db.min_cash(settings.new_low_days))}
     &nbsp;|&nbsp; <b>Mínima (milhas, {settings.new_low_days}d):</b>
     {_fmt_int(db.min_miles(settings.new_low_days))} milhas</p>

  <h2>💵 Melhores em dinheiro</h2>
  {_table_html(cash, "cash")}

  <h2>✈️ Melhores em milhas</h2>
  {_table_html(miles, "miles")}

  <h2>📈 Tendência (melhor por dia)</h2>
  <table cellpadding='6' style='border-collapse:collapse;width:100%;font-size:13px'>
    <tr style='background:#444;color:#fff;text-align:left'>
      <th>Dia</th><th>Melhor dinheiro</th><th>Melhor milhas</th></tr>
    {trend or "<tr><td colspan=3 style='color:#888'>Sem histórico ainda.</td></tr>"}
  </table>
</body></html>"""

    with open(settings.report_path, "w", encoding="utf-8") as f:
        f.write(html)
    return settings.report_path
