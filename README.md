# ✈️ Monitor de Passagens — Fortaleza (FOR) ⇄ Belo Horizonte (CNF)

Monitora os preços de passagens **ida e volta**, **sem data fixa** (varre vários
dias e durações de viagem à frente), guarda o histórico e te avisa **por e-mail**
quando o preço fica baixo — em **dinheiro** (via Amadeus) e em **milhas** (via Smiles).

> A ideia é: você não escolhe a data, o app procura *quando* fica barato.

---

## 1. Instalação (uma vez só)

Abra o **PowerShell** na pasta do projeto e rode:

```powershell
cd "C:\Users\tayna.TAYNA-PC\monitor-passagens"
py -3.12 -m venv .venv            # cria o ambiente isolado
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 2. Testar agora (sem precisar de nenhuma chave)

O arquivo `.env` já vem em **modo simulado** (`USE_SAMPLE_DATA=true`). Rode:

```powershell
.\.venv\Scripts\python.exe main.py run
.\.venv\Scripts\python.exe main.py report
```

Isso gera dados de teste, salva no banco e cria o relatório em `data\relatorio.html`
(abra no navegador). Assim você vê o app inteiro funcionando antes de plugar as APIs.

## 3. Ligar os preços REAIS

### a) Dinheiro (Travelpayouts — grátis, recomendado)
> A Amadeus foi descartada porque o portal gratuito dela será **desligado em
> julho/2026**. O Travelpayouts é gratuito, sustentável e varre meses inteiros.
1. Crie conta em https://www.travelpayouts.com (pode traduzir a página no Chrome).
2. No painel, vá em **Ferramentas/Tools → API** e copie o **token de acesso** (Data API).
3. Rode:
   ```powershell
   .\.venv\Scripts\python.exe main.py travelpayouts-setup --token SEU_TOKEN
   ```
   Isso salva o token, liga o modo real e já faz um teste de busca.

> Os preços do Travelpayouts são "cacheados" (do que outros usuários acharam
> recentemente), ótimos para detectar quedas. Sempre confirme no site da
> companhia antes de comprar. *(Alternativa: dá para usar a Amadeus pondo
> `CASH_PROVIDER=amadeus` e as chaves no `.env`, enquanto ela existir.)*

### b) Milhas (Smiles — instável)
A Smiles não tem API pública oficial. O app usa o mesmo endpoint que o site
chama. Você precisa colar a `x-api-key` atual:
1. Abra `smiles.com.br` no Chrome e faça uma busca de voos.
2. `F12` → aba **Network** → filtre por `search` → clique na chamada
   `.../airlines/search` → **Request Headers** → copie o valor de `x-api-key`.
3. Cole em `SMILES_API_KEY` no `.env`.
> Se um dia parar de funcionar, é só repetir esse passo. O monitoramento em
> dinheiro continua normal mesmo se as milhas falharem.

### c) Alertas no Telegram (mais fácil e instantâneo — recomendado)
O alerta chega como notificação no celular, na hora. Passo a passo:
1. No Telegram, procure **@BotFather**, mande `/newbot` e siga as perguntas.
   No fim ele te dá um **token** (algo como `123456:ABC-DEF...`).
2. Abra o **seu novo bot** e mande qualquer mensagem pra ele (ex.: "oi").
3. Rode:
   ```powershell
   .\.venv\Scripts\python.exe main.py telegram-setup --token SEU_TOKEN_AQUI
   ```
   O app descobre seu "chat id" sozinho, salva tudo e manda uma mensagem de teste.

### d) Alertas por e-mail (Gmail — opcional)
1. Ative verificação em 2 etapas na conta Google.
2. Gere uma **Senha de app**: myaccount.google.com → Segurança → Senhas de app.
3. No `.env`: `SMTP_USER`, `SMTP_PASS` (a senha de app), `EMAIL_TO`.
4. Teste: `.\.venv\Scripts\python.exe main.py test-email`

> Pode usar Telegram, e-mail, ou os dois ao mesmo tempo.

## 4. Usar no dia a dia

```powershell
.\.venv\Scripts\python.exe main.py run        # um ciclo (busca + alerta)
.\.venv\Scripts\python.exe main.py report     # ver melhores preços + HTML
.\.venv\Scripts\python.exe main.py loop --minutes 360   # roda sozinho a cada 6h
```

Registrar manualmente uma oferta de milhas que você viu (backup):
```powershell
.\.venv\Scripts\python.exe main.py add-miles --depart 2026-08-10 --ret 2026-08-17 --miles 15000 --fees 92.50 --airline G3
```

## 5. Deixar rodando automático (Agendador de Tarefas do Windows)

1. Abra **Agendador de Tarefas** → *Criar Tarefa Básica*.
2. Disparador: diário, repetir a cada algumas horas.
3. Ação: *Iniciar um programa* → selecione `run_monitor.bat` desta pasta.
4. Pronto: ele roda sozinho e te manda e-mail quando achar preço baixo.

> Observação: o PC precisa estar ligado na hora agendada. Se quiser que rode
> 24/7 mesmo com o PC desligado, dá para hospedar na nuvem depois.

## Ajustes úteis (no `.env`)
- `CASH_THRESHOLD` / `MILES_THRESHOLD`: a partir de quanto você quer ser avisada.
- `START_DAYS` / `END_DAYS`: o intervalo de datas que ele procura.
- `TRIP_NIGHTS`: durações de viagem (ex.: `4,7,10` noites).
- `STEP_DAYS` / `MAX_PAIRS`: granularidade x consumo de cota da API.

## Estrutura
```
config.py        configurações (lê o .env)
models.py        estrutura das ofertas + geração das datas
db.py            banco SQLite (histórico + alertas)
providers/       amadeus (dinheiro), smiles (milhas), sample (teste)
alerts/          envio de e-mail
monitor.py       junta tudo e decide o que vira alerta
report.py        relatório no terminal e em HTML
main.py          linha de comando
```

## Aviso
Preços e milhas mudam a cada minuto. O app é um **assinalador de oportunidades** —
sempre confirme o valor no site da companhia/Smiles antes de comprar. O acesso
aos dados de milhas usa um endpoint interno da Smiles e pode quebrar quando eles
mudarem algo; nesse caso, atualize a `x-api-key` ou registre as ofertas com
`add-miles`.
```
