# PRD — ZapPedidos Multi-Tenant (v2)

## Problema original
Continuar o projeto ZapPedidos, transformando em painel único para revenda com:
painel administrativo, painel do cliente, conexão fácil de WhatsApp (WAHA/Evolution),
CRUD de produtos, integração LAD Delivery v1 e visão de pedidos e conversas.
Hospedado em VPS via docker-compose.

## Personas
- Administrador geral: controla toda a operação, cadastra lojas e planos.
- Revendedor: cadastra e acompanha lojas clientes.
- Cliente/lojista: gerencia loja, catálogo, conecta o próprio WhatsApp, vê pedidos e conversas.

## Decisões de arquitetura
- React + FastAPI + MongoDB.
- JWT em cookie httpOnly (secure=True em produção HTTPS), separação por role/client_id.
- Cada loja tem sua sessão WhatsApp isolada (WAHA ou Evolution — provider é escolhido no painel).
- QR code lido diretamente do provider e devolvido em base64 para o painel.
- Polling automático de status a cada 5s enquanto qr_pending.
- Token LAD por loja (nunca retornado nas respostas públicas).
- LAD API v1: /loja, /cardapio, /frete, /pedidos com idempotencyKey obrigatório.
- Webhooks WhatsApp gravam mensagens locais para exibir conversas no painel.
- Limites de plano aplicados ao criar loja (Essencial 3, Crescimento 15, Escala ilimitado).

## Implementado (v2 — Fev/2026)
- Login/logout com JWT cookie httpOnly + bloqueio de brute force (5 tentativas).
- Seed automático do admin geral.
- Dashboard com métricas em tempo real (lojas, conectadas, planos, bots).
- CRUD completo de lojas (admin) + delete cascata (produtos, pedidos, chats).
- CRUD completo de produtos (create, list, update, delete, toggle ativo).
- Importação de cardápio LAD → catálogo local.
- WhatsApp provider unificado (WAHA + Evolution API) com QR real em base64.
- Setup / status / QR / disconnect endpoints unificados.
- Endpoints LAD: loja, cardapio, frete, criar_pedido, refresh pedido.
- Página Pedidos: lista e atualiza status via LAD.
- Página Conversas: exibe mensagens recebidas via webhook.
- Configurações: bot ativo, token LAD, URL do webhook para copiar.
- docker-compose.yml pronto para VPS (mongo + backend + frontend + WAHA + Evolution).
- Migração automática dos campos legados waha_* → wa_*.
- Limites de plano validados na criação de loja.

## Backlog priorizado
- P1: Cobrança automática por plano (Stripe/Mercado Pago) — próxima rodada.
- P1: Envio de mensagens do painel (WhatsApp → cliente) direto pelo chat.
- P2: Assinaturas HMAC nos webhooks (produção).
- P2: Convites de revendedores e relatórios financeiros.
- P2: Editor de opcionais/tamanhos de produto (grupos LAD).

## Endpoints principais
- POST /api/auth/login | logout | GET /me
- GET /api/dashboard
- CRUD /api/stores
- CRUD /api/stores/{id}/products
- POST /api/stores/{id}/lad/cardapio/importar
- GET /api/stores/{id}/whatsapp | POST /setup | GET /qr | POST /disconnect
- LAD: /lad/loja | /lad/cardapio | /lad/frete | /lad/pedidos
- /orders | /chats
- POST /api/webhooks/whatsapp/{store_id}  (WAHA/Evolution → backend)
