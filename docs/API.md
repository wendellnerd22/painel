# Referência da API — ZapPedidos

Base URL: `https://SEU_DOMINIO/api`

Autenticação: cookie httpOnly `zp_session` (JWT HS256, 7 dias). Todas as rotas exceto `/health`, `/auth/login` e webhooks exigem sessão. `secure=True` (só via HTTPS).

Papéis: `admin`, `reseller` (staff), `client`.

---

## Autenticação

### POST `/api/auth/login`
```json
{ "email": "admin@zappedidos.com", "senha": "Zap@2026" }
```
Resposta 200 com dados do usuário e cookie `zp_session` setado. Após 5 falhas em ~1 min: 429 por 15 minutos.

### POST `/api/auth/logout`
Limpa o cookie. Resposta 204.

### GET `/api/auth/me`
Retorna o usuário logado.

---

## Dashboard e Planos

### GET `/api/dashboard`
```json
{ "lojas": [...], "total": 3, "conectadas": 1, "planos": 2 }
```
Filtra pelas lojas visíveis ao papel logado.

### GET `/api/plans`
Lista os 3 planos padrão: Essencial (3 lojas), Crescimento (15), Escala (ilimitado).

---

## Lojas

### GET `/api/stores`
Lista lojas (admin vê todas; cliente vê as próprias).

### POST `/api/stores` — só staff
```json
{
  "nome": "Ponto do Açaí",
  "cliente_email": "cliente@empresa.com",
  "cliente_senha": "senhaInicial123",
  "plano": "Essencial",
  "lad_token": ""
}
```
Cria a loja E o usuário cliente. Bloqueia 402 se o cliente estourar o limite do plano.

### GET `/api/stores/{id}`
Detalhes com flags derivadas: `has_lad_token`, `has_wa_config`, `has_mp_token`, `mp_environment`.

### PATCH `/api/stores/{id}`
Admin altera qualquer campo. Cliente só pode mudar `bot_ativo` e `lad_token`.
```json
{ "bot_ativo": true, "lad_token": "novo-bearer" }
```

### DELETE `/api/stores/{id}` — só staff
Remove a loja e cascade em produtos/pedidos/chats. 204.

---

## Catálogo de Produtos

### GET `/api/stores/{id}/products`
Lista os produtos da loja.

### POST `/api/stores/{id}/products`
```json
{ "nome": "X-Bacon", "descricao": "Pão, hambúrguer, bacon", "preco": 34.9, "categoria": "Lanches", "ativo": true }
```

### PATCH `/api/stores/{id}/products/{product_id}`
Atualiza qualquer campo. Use `{"ativo": false}` para desativar.

### DELETE `/api/stores/{id}/products/{product_id}`
204.

---

## WhatsApp (WAHA / Evolution)

Provider abstrato: um único conjunto de endpoints atende os dois.

### GET `/api/stores/{id}/whatsapp`
```json
{ "status": "qr_pending", "raw": "SCAN_QR_CODE", "provider": "waha", "session": "zp_abc", "configured": true }
```
Status possíveis: `not_configured`, `not_started`, `pending`, `qr_pending`, `connected`, `offline`, `error`.

### POST `/api/stores/{id}/whatsapp/setup`
```json
{ "provider": "waha", "base_url": "https://waha.seu.com", "api_token": "chave", "session_name": "" }
```
Provider: `waha` ou `evolution`. Se `session_name` vazio, gera `zp_<store_id_prefix>`. Falhas de rede retornam 200 com `status: "error"` (nunca 500).

### GET `/api/stores/{id}/whatsapp/qr`
```json
{ "qr": "data:image/png;base64,iVBOR...", "status": "qr_pending", "message": "QR code atualizado." }
```
Se já conectado, `qr: null` e `status: "connected"`.

### POST `/api/stores/{id}/whatsapp/disconnect`
Encerra a sessão no provider e marca `wa_status = offline`.

### POST `/api/webhooks/whatsapp/{store_id}` — público
Recebe eventos WAHA/Evolution. Aceita ambos os formatos (WAHA: `body.text`, `body.from`, `fromMe`; Evolution: `data.key.remoteJid`, `data.message.conversation`). Grava em `db.chats`.

---

## LAD Delivery v1

Requer `lad_token` cadastrado na loja. Todos retornam 400 se não houver token, ou o erro do LAD verbatim.

### GET `/api/stores/{id}/lad/loja`
Dados da loja no LAD.

### GET `/api/stores/{id}/lad/cardapio`
Cardápio completo com categorias, produtos, tamanhos e opcionais.

### POST `/api/stores/{id}/lad/cardapio/importar`
Baixa o cardápio e cria/atualiza produtos locais.
```json
{ "importados": 12, "atualizados": 3, "categorias": 4 }
```

### POST `/api/stores/{id}/lad/frete`
Encapsula `POST /v1/frete`.
```json
{ "endereco": { "cep": "90000-000", "numero": "123" } }
```

### POST `/api/stores/{id}/lad/pedidos`
Encapsula `POST /v1/pedidos`. Se `idempotencyKey` não vier no payload, é gerado automaticamente.
```json
{ "payload": { "tipo": "DELIVERY", "itens": [...], "pagamento": {"forma": "PIX"} } }
```
Grava o pedido em `db.orders`. A resposta é o JSON do LAD verbatim.

### GET `/api/stores/{id}/orders`
Lista pedidos locais (sem o campo `raw`).

### POST `/api/stores/{id}/orders/{order_id}/refresh`
Consulta o status atualizado no LAD e atualiza local.

---

## Mercado Pago

Cada loja tem seu próprio Access Token, guardado **criptografado com Fernet** e nunca retornado.

### POST `/api/stores/{id}/mercadopago/setup`
```json
{ "access_token": "APP_USR-...", "ambiente": "producao" }
```
Ambientes: `producao` ou `teste`.

### GET `/api/stores/{id}/mercadopago`
```json
{ "configured": true, "ambiente": "teste" }
```

### DELETE `/api/stores/{id}/mercadopago`
Remove o token. 204.

### POST `/api/stores/{id}/mercadopago/pix` — cria cobrança PIX
```json
{ "valor": 39.90, "descricao": "Pedido #123", "email_pagador": "cliente@x.com", "referencia_externa": "pedido-123" }
```
Resposta:
```json
{
  "id": 1234567890,
  "status": "pending",
  "copia_e_cola": "00020126...",
  "qr_code_base64": "iVBOR...",
  "ticket_url": "https://...",
  "referencia": "pedido-123"
}
```
Sem token → 400. Token inválido → 401 (repassado do MP).

### POST `/api/stores/{id}/mercadopago/checkout` — cria preference (Checkout Pro)
```json
{
  "itens": [
    { "titulo": "X-Bacon", "quantidade": 1, "preco_unitario": 34.9 }
  ],
  "email_pagador": "cliente@x.com",
  "referencia_externa": "pedido-124"
}
```
Resposta:
```json
{
  "id": "1234567890-abc",
  "init_point": "https://www.mercadopago.com.br/checkout/...",
  "sandbox_init_point": "https://sandbox.mercadopago.com.br/checkout/...",
  "referencia": "pedido-124"
}
```

### GET `/api/stores/{id}/mercadopago/pagamentos`
Lista todas as tentativas de pagamento registradas.

### POST `/api/webhooks/mercadopago/{store_id}` — público
Aceita Webhook JSON (`{type, data.id}`) e IPN query (`?topic=payment&id=...`). Consulta `GET /v1/payments/{id}` no MP com o token da loja e atualiza `db.payments`.

---

## Conversas

### GET `/api/stores/{id}/chats`
Mensagens recebidas via webhook agrupadas por contato remoto.
```json
[{ "remote": "5511999...", "ultima": "Oi, quero um X-Bacon", "quando": "...", "mensagens": [...] }]
```

---

## Códigos de erro

| Código | Significado |
|---|---|
| 400 | Dados inválidos ou pré-condição faltando (ex.: sem token LAD/MP) |
| 401 | Sessão expirada/inválida |
| 402 | Limite do plano estourado |
| 403 | Papel não permite operação (ex.: cliente tentando criar loja) |
| 404 | Loja/produto/pedido não encontrado |
| 429 | Brute force lockout |
| 5xx do MP/LAD | Repassados com detail preservado |

---

## Modelo de dados (Mongo)

### `users`
```
{ id, email, password_hash, nome, role, created_at }
```

### `stores`
```
{
  id, nome, cliente_email, client_id, plano, status, bot_ativo, created_at,
  lad_token,                                       # bearer LAD
  wa_provider, wa_url, wa_token, wa_session, wa_status,
  mp_token_enc, mp_environment                     # Fernet encrypted
}
```

### `products`
```
{ id, store_id, nome, descricao, preco, categoria, ativo, lad_id?, imagem_url?, created_at }
```

### `orders`
```
{ id, store_id, uuid_lad, status, valor_total, tipo, itens, pagamento, raw, created_at }
```

### `chats`
```
{ id, store_id, remote, text, from_me, created_at }
```

### `payments`
```
{ id, store_id, mp_id, tipo (pix/checkout), status, valor, referencia_externa, created_at, updated_at? }
```

---

## Exemplo de fluxo completo (curl)

```bash
API=https://SEU_DOMINIO/api
JAR=/tmp/zp.txt

# 1. Login
curl -c $JAR -s -X POST $API/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@zappedidos.com","senha":"Zap@2026"}'

# 2. Criar loja
curl -b $JAR -s -X POST $API/stores \
  -H "Content-Type: application/json" \
  -d '{"nome":"Loja Teste","cliente_email":"c@teste.com","cliente_senha":"cliente123","plano":"Essencial"}'

# use o "id" retornado abaixo:
STORE_ID=...

# 3. Configurar WhatsApp
curl -b $JAR -s -X POST $API/stores/$STORE_ID/whatsapp/setup \
  -H "Content-Type: application/json" \
  -d '{"provider":"waha","base_url":"https://waha.seu.com","api_token":"CHAVE"}'

# 4. Pegar QR code
curl -b $JAR -s $API/stores/$STORE_ID/whatsapp/qr

# 5. Cadastrar MP
curl -b $JAR -s -X POST $API/stores/$STORE_ID/mercadopago/setup \
  -H "Content-Type: application/json" \
  -d '{"access_token":"APP_USR-...","ambiente":"producao"}'

# 6. Criar PIX
curl -b $JAR -s -X POST $API/stores/$STORE_ID/mercadopago/pix \
  -H "Content-Type: application/json" \
  -d '{"valor":10,"descricao":"Teste","email_pagador":"cliente@x.com"}'
```
