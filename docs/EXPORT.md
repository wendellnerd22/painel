# Como exportar o código do ZapPedidos

Você tem duas formas de baixar o código: **GitHub (recomendado)** ou **download ZIP direto**.

---

## Opção 1 — Exportar para o GitHub (recomendado)

Vantagens: histórico versionado, deploy contínuo, colaboração fácil.

### 1. Prepare o repositório GitHub
1. Crie uma conta em [github.com](https://github.com) (grátis).
2. Clique em **New repository** → nome ex.: `zappedidos` → privado ou público → **NÃO marque** "Initialize with README" → **Create repository**.
3. Copie a URL SSH ou HTTPS que aparece (ex.: `https://github.com/seuuser/zappedidos.git`).

### 2. Conecte pelo Emergent
1. Abra seu projeto no [Emergent](https://emergent.sh).
2. No canto superior direito, clique no botão **Code** ou **GitHub**.
3. Se aparecer **Connect GitHub**, faça login e autorize o acesso.
4. Selecione o repositório criado no passo anterior.
5. Clique em **Push to GitHub**.

Pronto. Todo o código de `/app` (backend, frontend, docs, docker-compose) vai para o seu repositório.

### 3. Clone na sua VPS ou máquina local

```bash
git clone https://github.com/seuuser/zappedidos.git
cd zappedidos
```

Siga o [`DEPLOY.md`](DEPLOY.md) para subir em VPS ou o `README.md` para rodar localmente.

---

## Opção 2 — Download direto (ZIP)

Se você não quer usar GitHub agora:

1. No Emergent, abra o projeto.
2. Clique em **Code** → **Download ZIP** (canto superior direito).
3. Extraia o arquivo em qualquer pasta.

O ZIP contém a mesma estrutura que o repositório: `backend/`, `frontend/`, `docs/`, `docker-compose.yml`, `.env.example`.

---

## O que você recebe

```
zappedidos/
├── backend/
│   ├── server.py            ← toda a API (~1030 linhas)
│   ├── requirements.txt
│   ├── .env.example         ← copie para .env e ajuste
│   └── tests/
├── frontend/
│   ├── src/App.js           ← todo o painel React
│   ├── src/App.css
│   ├── package.json
│   └── .env
├── docs/
│   ├── DEPLOY.md
│   ├── API.md
│   └── EXPORT.md            ← este arquivo
├── docker-compose.yml       ← stack completa
├── .env.example
└── README.md
```

---

## Checklist pós-clone

Antes de subir na VPS ou executar em produção, verifique:

- [ ] `cp .env.example .env` na raiz e edite `FRONTEND_URL`, `JWT_SECRET`, `ADMIN_PASSWORD`, chaves WAHA/Evolution
- [ ] `backend/.env` contém `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `TOKEN_ENCRYPTION_KEY` (gere com `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- [ ] `frontend/.env` contém `REACT_APP_BACKEND_URL` com a URL HTTPS pública
- [ ] Domínios apontam para a VPS (DNS A record) — necessário para o Certbot
- [ ] Portas 80 e 443 abertas no firewall

---

## Segredos que **NUNCA** devem ir pro repositório público

Se o repositório for público, garanta que estes arquivos estão no `.gitignore`:

```
.env
backend/.env
frontend/.env
```

O `.gitignore` do projeto já ignora esses arquivos por padrão. Antes de dar push confirme:

```bash
git status
# não deve aparecer nenhum .env
```

Se acidentalmente enviou um `.env` com segredos, gire todos:
- Senha do admin
- `JWT_SECRET`
- `TOKEN_ENCRYPTION_KEY` (⚠️ isso invalida tokens MP salvos — reconfigure em cada loja)
- Chave WAHA / Evolution
- Access Tokens do Mercado Pago dos clientes

---

## Atualizando o código depois

Sempre que fizer melhoria pelo Emergent ou localmente:

```bash
# No Emergent: clique em "Push to GitHub"
# Ou local:
git add .
git commit -m "descrição da mudança"
git push
```

Na VPS, para atualizar a versão em produção:

```bash
cd /opt/zappedidos
git pull
docker compose build --pull
docker compose up -d
```

---

## Perguntas frequentes

**P: Posso hospedar em Vercel/Netlify?**
R: O frontend sim (build `yarn build` da pasta `frontend`), mas o backend FastAPI precisa de um servidor Python (Railway, Render, Fly.io, VPS própria). Ajuste `REACT_APP_BACKEND_URL` para apontar para o backend em outro domínio e libere CORS.

**P: Preciso pagar Emergent para exportar?**
R: Não. A exportação para GitHub e o download ZIP são funcionalidades básicas e sempre gratuitas. Você é o dono do código.

**P: Perdi o `TOKEN_ENCRYPTION_KEY`. E agora?**
R: Tokens MP salvos ficam inacessíveis. Gere uma nova chave, reinicie o backend, e peça para cada cliente cadastrar o Access Token novamente na tela Configurações → Mercado Pago.

**P: Como faço rollback?**
R: `git log --oneline` para achar o commit anterior estável, depois `git checkout <hash>` na VPS e `docker compose up -d --force-recreate`.

**P: E se eu quiser migrar de MongoDB para outro banco?**
R: O código usa **Motor (async Mongo driver)**. Migrar exigiria reescrever `server.py`. Se for necessário, faça em fases: exporte JSON com `mongodump`, importe no novo banco, e substitua as chamadas `db.xxx.find(...)` por SQL/ORM equivalente.
