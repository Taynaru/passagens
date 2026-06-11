name: Monitor de Passagens
# Roda automaticamente a cada 6 horas (na nuvem do GitHub, de graça),
# mesmo com o seu computador desligado. Também dá pra rodar na mão pelo botão.
on:
  schedule:
    - cron: "0 */6 * * *"   # a cada 6 horas (horário UTC)
  workflow_dispatch:         # botão "Run workflow" para rodar quando quiser
    inputs:
      teste:
        description: "Enviar uma mensagem de TESTE no meu Telegram agora?"
        type: boolean
        default: false
# Necessário para salvar o histórico de preços de volta no repositório.
permissions:
  contents: write
# Evita que duas execuções rodem ao mesmo tempo (e conflitem no histórico).
concurrency:
  group: monitor-passagens
  cancel-in-progress: false
# Usa a versão nova do Node (silencia o aviso de "deprecation"; não muda o app).
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  monitorar:
    runs-on: ubuntu-latest
    steps:
      - name: Baixar o código
        uses: actions/checkout@v5
      - name: Preparar o Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Instalar dependências
        run: pip install -r requirements.txt
      - name: Rodar o monitor
        env:
          # --- Rota e janela de busca (não são segredos) ---
          ORIGIN: FOR
          DESTINATION: CNF
          ADULTS: "1"
          CURRENCY: BRL
          START_DAYS: "21"
          END_DAYS: "120"
          STEP_DAYS: "7"
          TRIP_NIGHTS: "4,7,10"
          # --- Provedores ---
          USE_SAMPLE_DATA: "false"
          CASH_PROVIDER: travelpayouts
          ENABLE_CASH: "true"
          ENABLE_MILES: "false"
          # --- Limiares de alerta ---
          CASH_THRESHOLD: "1100"
          ALERT_ON_NEW_LOW: "true"
          NEW_LOW_DAYS: "30"
          # --- Segredos (configurados em Settings -> Secrets do GitHub) ---
          TRAVELPAYOUTS_TOKEN: ${{ secrets.TRAVELPAYOUTS_TOKEN }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py run
      - name: Enviar mensagem de teste no Telegram (opcional)
        if: ${{ github.event.inputs.teste == 'true' }}
        env:
          ORIGIN: FOR
          DESTINATION: CNF
          CASH_THRESHOLD: "1100"
          START_DAYS: "21"
          END_DAYS: "120"
          TRIP_NIGHTS: "4,7,10"
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python main.py test-telegram
      - name: Salvar o histórico de preços
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -f data/precos.db
          git commit -m "Atualiza histórico de preços [skip ci]" || echo "Sem mudanças para salvar."
          git push || echo "Nada para enviar."
