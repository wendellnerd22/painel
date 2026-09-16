# ZapPedidos — automação de WhatsApp para delivery (LAD Delivery API v1)

## O que o app faz
SaaS de revenda: o revendedor cadastra várias lojas, cada uma com seu token da API
Pública LAD Delivery v1. Um bot de IA (Gemini 3 Flash via Emergent LLM key) conversa
com o cliente, consulta loja/cardápio, cota frete e cria o pedido na LAD.
Interface em pt-BR, tema escuro.

## Modo demonstração
Se a loja estiver marcada `demo` ou não tiver token, o backend responde com um cardápio
fictício (Du Cheff Burguer: X-Salada 320599, X-Bacon 320600, Pizza Calabresa 330100 com
tamanhos 4=Grande/5=Pequena, bebidas 340001/340002) e cria pedidos calculados localmente
(pedido mínimo R$20, frete R$7, formas DINHEIRO/PIX/CREDITO/DEBITO).

## Modelo de dados (Mongo)
- `stores`: id, nome, token, demo, bot_prompt, conexao_ok, conexao_msg, created_at
- `orders`: id (uuid do pedido LAD), store_id, session_id, cliente_nome, cliente_telefone,
  tipo, status_codigo (E/A/V/X/D/P/C/R), status_descricao, valor_total, data_pedido, demo, payload
- `chat_messages`: id, session_id, store_id, role (user|bot), text, tools[], created_at

## Endpoints (todos sob /api)
- GET/POST `/stores`, GET/PATCH/DELETE `/stores/{id}`
- POST `/stores/{id}/testar` → ConnectionResult
- GET `/stores/{id}/loja`, `/stores/{id}/cardapio` (proxy LAD)
- GET `/stores/{id}/pedidos`, POST `/stores/{id}/pedidos/{uuid}/atualizar`
- POST `/chat/{store_id}` {session_id, message} → {reply, tools[], order_uuid}
- GET/DELETE `/chat/{store_id}/{session_id}` (histórico / reset)

## Fluxos
1. `/` cadastra loja (nome, token, modo demo, prompt extra) → teste de conexão automático.
2. `/lojas/:id` abas Visão geral, Cardápio, Pedidos do bot (status coloridos + atualizar).
3. `/simulador?loja=<id>` chat estilo WhatsApp + inspetor das chamadas à API LAD.
4. `/whatsapp` instruções de conectores open source (Baileys, Evolution API, WPPConnect).

## Auth
Sessão por cookie httpOnly (JWT, `zp_session`), rotas em `/api/auth/*`
(`POST /auth/login`, `POST /auth/logout`, `GET /auth/me`). Frontend usa `lib/session.ts`
(`useMe`, `beginSession`, `endSession`) e `/login` como página pública.

Papéis:
- **admin (revendedor)**: CRUD de lojas, vê token LAD e api_key, cria o usuário do lojista
  (e-mail + senha no formulário da loja), acessa todas as páginas.
- **lojista**: só a própria loja (`user.store_id`) — visão geral, cardápio, pedidos e simulador.
  Token LAD e api_key vêm mascarados; PATCH aceita apenas `bot_prompt`; DELETE retorna 403.

Coleção `users`: id, email, nome, role, store_id, senha_hash (bcrypt/passlib), created_at.
Admin inicial semeado no lifespan: admin@zappedidos.com / Zap@2026.

Conector WhatsApp: `POST /api/chat/{store_id}` autoriza por sessão OU header `X-API-Key`
igual ao `stores.api_key`.

## Observações
- O token LAD fornecido pelo usuário (e1caf...31) retorna 401 na API real; por isso o modo
  demonstração é o caminho de teste.
- O chat é não-streaming (mensagem inteira), igual ao comportamento do WhatsApp.
- Histórico do LlmChat é mantido em memória por sessão no processo do backend; as mensagens
  visíveis são persistidas no Mongo.
