# ZapPedidos — Painel Multi-Tenant WhatsApp + Delivery

Plataforma SaaS de revenda: um painel único onde **você (revendedor)** cadastra clientes/lojas e cada **cliente lojista** conecta o próprio WhatsApp, gerencia catálogo, recebe pedidos pela API LAD Delivery e cobra via Mercado Pago.

---

## Sumário

- [O que é](#o-que-é)
- [Arquitetura](#arquitetura)
- [Funcionalidades](#funcionalidades)
- [Stack técnica](#stack-técnica)
- [Estrutura de pastas](#estrutura-de-pastas)
- [Como rodar localmente](#como-rodar-localmente)
- [Documentos relacionados](#documentos-relacionados)
- [Credenciais iniciais](#credenciais-iniciais)

---

## O que é

**ZapPedidos** é uma ferramenta que você vende como serviço: cada cliente que assina recebe um acesso ao painel para operar sua loja de delivery via WhatsApp. O painel resolve três coisas que normalmente exigem 3 sistemas diferentes:

1. **Conectar o WhatsApp do cliente** de forma fácil, isolada e com opção anti-ban (WAHA ou Evolution API).
2. **Sincronizar o cardápio e criar pedidos** via API pública LAD Delivery v1.
3. **Receber pagamentos** via PIX ou Checkout Pro do Mercado Pago, com o token de cada cliente guardado criptografado.

Tudo no mesmo painel, com **isolamento multi-tenant** garantido: o cliente A nunca vê os dados do cliente B.

---

## Arquitetura

```
┌────────────────────┐          ┌────────────────────┐
│  Painel React      │◀────────▶│  API FastAPI       │
│  (admin + cliente) │  HTTPS   │  (roteamento /api) │
└────────────────────┘          └─────┬──────────────┘
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                  ▼
              ┌───────────┐    ┌───────────┐      ┌────────────┐
              │  MongoDB  │    │  WAHA ou  │      │   LAD API  │
              │(multi-    │    │ Evolution │      │  v1        │
              │ tenant)   │    │ (WhatsApp)│      │            │
              └───────────┘    └───────────┘      └────────────┘
                                                    │
                                      ┌─────────────┴───────────┐
                                      ▼                         ▼
                              ┌───────────────┐        ┌────────────────┐
                              │ Mercado Pago  │        │  Webhooks IN   │
                              │ (por loja)    │        │  (WA + MP)     │
                              └───────────────┘        └────────────────┘
```

- **Frontend**: SPA React que consome apenas `/api/*` do backend próprio.
- **Backend**: FastAPI. Um único arquivo `server.py` com routers, auth JWT em cookie httpOnly e helpers para cada integração externa.
- **MongoDB**: coleções `users`, `stores`, `products`, `orders`, `chats`, `payments`, `login_attempts`.
- **WhatsApp**: WAHA e Evolution rodam como containers separados; o painel só guarda `wa_url` + `wa_token` + `wa_session` de cada loja.
- **LAD Delivery**: chamada HTTP direta usando `Bearer` guardado por loja.
- **Mercado Pago**: token criptografado com **Fernet**; PIX + Checkout Pro via REST puro.

### Modelo de papéis

| Papel | O que vê / faz |
|---|---|
| **admin** | Todas as lojas, cria/exclui lojas e clientes, altera planos, vê tudo. |
| **reseller** | Igual ao admin (mesmo bloco de permissões). Reservado para futura hierarquia de revendedores múltiplos. |
| **client** | Só a própria loja. Configura WhatsApp, catálogo, LAD token, MP token, vê pedidos e conversas. |

### Multi-tenant

Cada loja tem `client_id`. Toda query de dados sensíveis (`/products`, `/orders`, `/chats`, `/payments`) é filtrada por `store_id` e, para o role `client`, adicionalmente por `client_id`. O helper `get_store()` centraliza esse filtro — impossível esquecer.

---

## Funcionalidades

### Painel do administrador
- CRUD de lojas com criação automática de acesso do cliente (e-mail + senha)
- Métricas em tempo real (lojas ativas, WhatsApps conectados, planos em uso)
- Gerenciamento de planos (Essencial 3 lojas, Crescimento 15, Escala ilimitado)
- Exclusão em cascata (produtos, pedidos, chats)

### Painel do cliente
- Login isolado (só vê a própria loja)
- Configuração do WhatsApp com **provider selecionável** (WAHA ou Evolution)
- QR code **real em base64** com polling automático a cada 5 s
- CRUD completo do catálogo (criar, editar, excluir, ativar/desativar)
- **Importação do cardápio LAD Delivery** com 1 clique
- Página Pedidos com refresh de status via LAD
- Página Conversas com mensagens agrupadas por contato (webhook)
- Configuração do Access Token do Mercado Pago com teste de PIX de R$ 1,00

### Segurança
- Senhas hash com bcrypt
- JWT em cookie httpOnly `zp_session` (+ `secure=True` em HTTPS)
- Bloqueio de brute force (5 tentativas → 15 min de lockout)
- Access Token do MP guardado criptografado com **Fernet**
- Nenhum token/segredo aparece em respostas da API
- Isolamento por role + `client_id` em todas as rotas

### DevOps
- `docker-compose.yml` pronto para VPS com WAHA + Evolution + Mongo + backend + frontend
- Migração automática de campos legados
- Health check em `/api/health`

---

## Stack técnica

| Camada | Tecnologia | Motivo |
|---|---|---|
| Frontend | React 19 + React Router + Axios | SPA rápida, roteamento simples |
| UI | CSS custom com paleta teal + Lucide React (ícones) | Sem framework pesado, identidade própria |
| Backend | FastAPI + Motor (Mongo async) | Async nativo, tipagem Pydantic |
| Auth | JWT + cookie httpOnly + bcrypt | Padrão seguro para SPA |
| DB | MongoDB 7 | Schemaless combina com multi-tenant |
| WhatsApp | WAHA (devlikeapro) ou Evolution API | Self-hosted, sem custo por número |
| Delivery | LAD Delivery v1 | Cardápio, frete, pedidos oficiais |
| Pagamento | Mercado Pago (REST + Fernet) | PIX + Checkout Pro sem SDK |
| Deploy | Docker Compose | 1 comando pra subir tudo |

---

## Estrutura de pastas

```
/app
├── backend/
│   ├── server.py            # Toda a API em um arquivo (~1030 linhas)
│   ├── requirements.txt     # Dependências Python
│   ├── .env                 # MONGO_URL, DB_NAME, TOKEN_ENCRYPTION_KEY, JWT_SECRET
│   └── tests/               # Pytest (regressão + Mercado Pago)
├── frontend/
│   ├── src/
│   │   ├── App.js           # Toda a UI (~890 linhas)
│   │   ├── App.css          # Estilos
│   │   └── index.js
│   ├── package.json
│   └── .env                 # REACT_APP_BACKEND_URL
├── memory/
│   ├── PRD.md               # Roadmap e histórico
│   └── test_credentials.md  # Contas de teste
├── docs/                    # Esta documentação
│   ├── DEPLOY.md
│   ├── API.md
│   └── EXPORT.md
├── docker-compose.yml       # Stack completa para VPS
├── .env.example
└── README.md
```

---

## Como rodar localmente

Requisitos: Docker + Docker Compose ou Python 3.11 + Node 20 + MongoDB local.

### Opção A — Docker Compose (recomendado)

```bash
cp .env.example .env
# edite os tokens do WAHA e Evolution
docker compose up -d
```

Acesse:
- Painel ZapPedidos: http://localhost
- API: http://localhost:8001/api/health
- WAHA Dashboard: http://localhost:3001 (usuário `admin`/senha em `.env`)
- Evolution API: http://localhost:8080

### Opção B — Local sem Docker

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env já vem preenchido no repo (ajuste MONGO_URL se necessário)
uvicorn server:app --reload --port 8001

# Frontend (em outro terminal)
cd frontend
yarn install
yarn start
# Painel abre em http://localhost:3000
```

---

## Documentos relacionados

| Documento | O que contém |
|---|---|
| [`docs/DEPLOY.md`](docs/DEPLOY.md) | Passo a passo pra subir em VPS Ubuntu com HTTPS |
| [`docs/API.md`](docs/API.md) | Referência de todos os endpoints com exemplos curl |
| [`docs/EXPORT.md`](docs/EXPORT.md) | Como exportar o código do Emergent pro seu GitHub |

---

## Credenciais iniciais

Ao subir pela primeira vez, o admin é criado automaticamente:

- **E-mail**: `admin@zappedidos.com`
- **Senha**: `Zap@2026`

⚠️ **Em produção, altere via variáveis `ADMIN_EMAIL` e `ADMIN_PASSWORD` no `.env` antes do primeiro start.** Se o e-mail já existir, a senha é atualizada em cada reinício — o que também serve para recuperar acesso.

---

## Licença e créditos

Projeto proprietário. Integrações:
- [WAHA](https://waha.devlike.pro/) — devlikeapro
- [Evolution API](https://evolution.mintlify.app/) — atendai
- [LAD Delivery API v1](https://api2.laddelivery.com.br)
- [Mercado Pago Developers](https://www.mercadopago.com.br/developers)
