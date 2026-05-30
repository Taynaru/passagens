"""Monitor de Passagens — Fortaleza (FOR) ⇄ Belo Horizonte (CNF).

Linha de comando:
  python main.py run            -> roda um ciclo (busca, salva, alerta)
  python main.py run --sample   -> idem, com dados simulados (sem chaves)
  python main.py run --no-email -> roda sem disparar e-mail
  python main.py loop           -> roda em laço (intervalo de LOOP_MINUTES)
  python main.py report         -> mostra os melhores preços e gera o HTML
  python main.py test-email     -> envia um e-mail de teste
  python main.py add-miles ...  -> registra manualmente uma oferta de milhas
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from config import load_settings
from db import Database
from models import Offer


def _setup_logging() -> None:
    # O console do Windows costuma ser cp1252 e quebra com emojis/acentos.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def cmd_run(args, settings, db) -> None:
    from monitor import run_cycle
    from report import write_html_report
    run_cycle(settings, db, force_sample=args.sample, send_alerts=not args.no_email)
    path = write_html_report(settings, db)
    print(f"\nRelatório atualizado: {path}")


def cmd_loop(args, settings, db) -> None:
    from monitor import run_cycle
    from report import write_html_report
    interval = max(args.minutes, 5) * 60
    log = logging.getLogger("loop")
    log.info("Iniciando laço: 1 ciclo a cada %d min. Ctrl+C para parar.", args.minutes)
    while True:
        try:
            run_cycle(settings, db, force_sample=args.sample, send_alerts=not args.no_email)
            write_html_report(settings, db)
        except KeyboardInterrupt:
            log.info("Encerrado pelo usuário.")
            break
        except Exception as e:  # noqa: BLE001
            log.error("Erro no ciclo: %s", e)
        time.sleep(interval)


def cmd_report(args, settings, db) -> None:
    from report import print_report, write_html_report
    print_report(settings, db)
    path = write_html_report(settings, db)
    print(f"Relatório HTML: {path}")


def cmd_test_email(args, settings, db) -> None:
    from alerts.email_alert import send_test_email
    ok = send_test_email(settings)
    print("E-mail de teste enviado!" if ok
          else "Não foi possível enviar. Verifique as configurações SMTP no .env.")


def cmd_test_telegram(args, settings, db) -> None:
    from alerts.telegram_alert import send_test_telegram
    ok = send_test_telegram(settings)
    print("Mensagem de teste enviada no Telegram!" if ok
          else "Não enviou. Rode 'telegram-setup' antes (veja as instruções).")


def cmd_telegram_setup(args, settings, db) -> None:
    """Configura o Telegram: salva o token e descobre o chat id sozinho."""
    from alerts.telegram_alert import fetch_chat_id, send_test_telegram
    from config import load_settings, set_env_value

    token = args.token or settings.telegram_bot_token
    if not token:
        print("Faltou o token. Use: python main.py telegram-setup --token SEU_TOKEN")
        print("(O token vem do @BotFather no Telegram, ao criar o bot com /newbot.)")
        return
    set_env_value("TELEGRAM_BOT_TOKEN", token)

    print("Procurando sua conversa com o bot...")
    chat_id = fetch_chat_id(token)
    if not chat_id:
        print("\nNão achei nenhuma mensagem ainda. Faça assim:")
        print("  1. Abra o Telegram e mande qualquer mensagem (ex.: 'oi') para o SEU bot.")
        print("  2. Rode este comando de novo:  python main.py telegram-setup")
        return
    set_env_value("TELEGRAM_CHAT_ID", chat_id)
    print(f"Tudo certo! Chat id encontrado e salvo ({chat_id}).")

    # recarrega as configurações já com token+chat_id e manda um teste
    new_settings = load_settings()
    if send_test_telegram(new_settings):
        print("Mandei uma mensagem de teste no seu Telegram. Confira o celular! ✅")
    else:
        print("Salvei tudo, mas o teste não foi. Tente 'python main.py test-telegram'.")


def cmd_travelpayouts_setup(args, settings, db) -> None:
    """Salva o token do Travelpayouts, liga o modo real e faz um teste."""
    from config import load_settings, set_env_value
    from providers.travelpayouts import TravelpayoutsProvider

    token = args.token or settings.travelpayouts_token
    if not token:
        print("Faltou o token. Use: python main.py travelpayouts-setup --token SEU_TOKEN")
        print("(O token vem do painel do Travelpayouts: Ferramentas -> API.)")
        return
    set_env_value("TRAVELPAYOUTS_TOKEN", token)
    set_env_value("CASH_PROVIDER", "travelpayouts")
    set_env_value("USE_SAMPLE_DATA", "false")
    print("Token salvo e modo real ligado. Fazendo um teste de busca...")

    new_settings = load_settings()
    offers = TravelpayoutsProvider(new_settings).search()
    if offers:
        print(f"\n✅ Funcionou! Encontrei {len(offers)} opções. As mais baratas:")
        for o in offers[:5]:
            print(f"   • {o.human()}")
        print("\nAgora é só rodar:  python main.py run")
    else:
        print("\n⚠️ O token foi salvo, mas a busca não trouxe resultados agora.")
        print("Pode ser falta de dados para a rota no momento. Tente "
              "'python main.py run' mais tarde.")


def cmd_add_miles(args, settings, db) -> None:
    """Registro manual de oferta em milhas (caso a coleta automática falhe)."""
    offer = Offer(
        provider="manual", fare_type="miles",
        origin=settings.origin, destination=settings.destination,
        depart_date=args.depart, return_date=args.ret,
        price=args.fees, miles=args.miles, airline=args.airline or "",
    )
    db.save_offers([offer])
    print(f"Registrado: {offer.human()}")


def main() -> None:
    _setup_logging()
    settings = load_settings()

    parser = argparse.ArgumentParser(description="Monitor de passagens FOR <-> CNF")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="roda um ciclo de monitoramento")
    p_run.add_argument("--sample", action="store_true", help="usa dados simulados")
    p_run.add_argument("--no-email", action="store_true", help="não envia e-mail")
    p_run.set_defaults(func=cmd_run)

    p_loop = sub.add_parser("loop", help="roda continuamente em intervalos")
    p_loop.add_argument("--minutes", type=int, default=360, help="intervalo (min)")
    p_loop.add_argument("--sample", action="store_true")
    p_loop.add_argument("--no-email", action="store_true")
    p_loop.set_defaults(func=cmd_loop)

    p_rep = sub.add_parser("report", help="mostra os melhores preços e gera HTML")
    p_rep.set_defaults(func=cmd_report)

    p_te = sub.add_parser("test-email", help="envia um e-mail de teste")
    p_te.set_defaults(func=cmd_test_email)

    p_tg = sub.add_parser("telegram-setup", help="configura os alertas por Telegram")
    p_tg.add_argument("--token", default="", help="token do bot (do @BotFather)")
    p_tg.set_defaults(func=cmd_telegram_setup)

    p_tt = sub.add_parser("test-telegram", help="envia uma mensagem de teste no Telegram")
    p_tt.set_defaults(func=cmd_test_telegram)

    p_tp = sub.add_parser("travelpayouts-setup",
                          help="configura a fonte de preços (Travelpayouts)")
    p_tp.add_argument("--token", default="", help="token do Travelpayouts")
    p_tp.set_defaults(func=cmd_travelpayouts_setup)

    p_am = sub.add_parser("add-miles", help="registra manualmente uma oferta de milhas")
    p_am.add_argument("--depart", required=True, help="data ida YYYY-MM-DD")
    p_am.add_argument("--ret", required=True, help="data volta YYYY-MM-DD")
    p_am.add_argument("--miles", type=int, required=True, help="total de milhas ida+volta")
    p_am.add_argument("--fees", type=float, default=0.0, help="taxas em R$")
    p_am.add_argument("--airline", default="", help="cia (ex.: G3)")
    p_am.set_defaults(func=cmd_add_miles)

    args = parser.parse_args()
    db = Database(settings.db_path)
    try:
        args.func(args, settings, db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
