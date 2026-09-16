# ZapPedidos — rodando localmente com Docker

## O que você precisa antes de começar

- **Docker Desktop** instalado (Windows/Mac) ou **Docker Engine + Docker Compose** (Linux)
- Uma chave gratuita do **Gemini**: https://aistudio.google.com/apikey
- (Opcional pra já testar pagamento de verdade) uma conta no **Mercado Pago Developers**
- (Opcional pra já testar WhatsApp de verdade) um número de WhatsApp à parte pra conectar

Nada mais — o Mongo, o WAHA e o Traccar já vêm dentro do `docker-compose.yml`.

## Passo 1 — Extrair os arquivos

Extraia o zip numa pasta. Você deve ver `backend/`, `frontend/`, `docker-compose.yml` e `.env.example` na raiz.

## Passo 2 — Criar o arquivo `.env`

```bash
cp .env.example .env
```

Abra o `.env` num editor de texto e preencha pelo menos:

| Variável | O que colocar |
|---|---|
| `SESSION_SECRET` | Um valor aleatório de 64 caracteres. Veja como gerar logo abaixo desta tabela, ou deixe em branco — o sistema gera um sozinho a cada reinício (funciona, mas desloga todo mundo quando reiniciar) |
| `GEMINI_API_KEY` | A chave que você criou em aistudio.google.com/apikey |
| `ADMIN_PASSWORD` | Uma senha forte para o seu login de revendedor. Se deixar em branco, o sistema gera uma sozinha e mostra **uma única vez** no log do backend (passo 5 explica como ver) |

**Como gerar o `SESSION_SECRET`:** escolha o que for mais fácil pra você e cole o resultado no `.env`, na linha `SESSION_SECRET=`.

- **Windows (PowerShell)** — abra o PowerShell (não precisa ser administrador) e rode:
  ```powershell
  -join ((48..57)+(97..102)|Get-Random -Count 64|%{[char]$_})
  ```
- **Mac ou Linux (Terminal)**:
  ```bash
  openssl rand -hex 32
  ```
  Se o comando `openssl` não existir (raro), use `python3 -c "import secrets; print(secrets.token_hex(32))"` no lugar.
- **Não quer usar terminal nenhum:** é só qualquer sequência aleatória de letras e números com uns 40-60 caracteres — pode digitar batendo no teclado sem pensar, tipo `kj3h4kJH34kjh34KJH34kjh34kjh34KJH34kjh34kjh`. O importante é ser longo e imprevisível; ninguém mais precisa saber esse valor.

Os campos de Mercado Pago (`MERCADOPAGO_ACCESS_TOKEN`, `MERCADOPAGO_WEBHOOK_SECRET`) e WAHA (`WAHA_API_KEY`, `WAHA_WEBHOOK_HMAC_KEY`) podem ficar em branco por enquanto — o sistema roda em modo simulado sem eles. Preencha quando quiser testar pagamento e WhatsApp de verdade.

## Passo 3 — Subir tudo

Na pasta onde está o `docker-compose.yml`:

```bash
docker compose up -d --build
```

A primeira vez demora alguns minutos (baixa as imagens do Mongo, WAHA, Traccar, e builda o backend/frontend). Se o build do frontend falhar tentando baixar `@emergentbase/visual-edits` ou `@emergentbase/overlay`, abra `frontend/package.json`, apague as duas linhas desses pacotes em `devDependencies`, e rode `docker compose up -d --build` de novo — o projeto já foi ajustado para funcionar sem eles.

## Passo 4 — Conferir se subiu tudo certo

```bash
docker compose ps
```

Todos os serviços devem aparecer como `running` (o `backend` e o `mongo` também mostram `healthy` depois de alguns segundos).

## Passo 5 — Pegar a senha do admin (se deixou em branco)

```bash
docker compose logs backend | grep "senha do admin"
```

Copie a senha que aparecer — ela só é mostrada essa vez.

## Passo 6 — Acessar cada serviço

| Serviço | Endereço | Login |
|---|---|---|
| **ZapPedidos (painel)** | http://localhost | `admin@zappedidos.com` + a senha do passo 5 |
| **API do backend** (documentação interativa) | http://localhost:8001/docs | — |
| **WAHA** (conectar o WhatsApp) | http://localhost:3001 | — |
| **Traccar** (rastreamento) | http://localhost:8082 | `admin` / `admin` (troque no primeiro acesso) |

## Passo 7 — Conectar o WhatsApp (WAHA)

1. Abra http://localhost:3001
2. Crie uma sessão com o nome igual ao **ID da loja** (você vê o ID na URL do painel quando abre a loja, ex.: `/lojas/<esse-id-aqui>`)
3. Escaneie o QR code com o WhatsApp que vai atender os pedidos
4. Nas configurações da sessão, confirme que o webhook aponta para `http://backend:8001/api/webhooks/waha` (já vem configurado pelo `docker-compose.yml`)

## Passo 8 — Conectar o rastreamento (Traccar)

Não precisa configurar nada manualmente — quando você criar a primeira rota de entrega pela tela "Rotas de entrega" do painel, o próprio backend cria o dispositivo do motoboy e o link de rastreamento no Traccar automaticamente.

## Comandos úteis

```bash
# ver os logs de um serviço específico em tempo real
docker compose logs -f backend

# parar tudo (sem apagar os dados)
docker compose stop

# subir de novo
docker compose start

# parar e apagar TUDO, incluindo os dados (Mongo, sessões do WhatsApp, rastreamento)
docker compose down -v
```

## Se algo não subir

```bash
docker compose logs backend    # erros do backend
docker compose logs frontend   # erros do build/nginx
docker compose logs mongo      # erros do banco
```

O endpoint `http://localhost:8001/api/health` responde `{"status":"ok"}` quando o backend está de pé e conseguindo falar com o Mongo — é o primeiro lugar pra checar se algo estiver estranho.
