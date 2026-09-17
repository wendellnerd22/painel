# Deploy do ZapPedidos em VPS

Guia passo a passo para colocar o painel + WhatsApp + Mongo em uma VPS Ubuntu 22.04 com HTTPS válido.

---

## Requisitos

- VPS com Ubuntu 22.04+ (mínimo 2 vCPU, 4 GB RAM, 40 GB SSD)
- Domínio apontando para o IP da VPS (ex.: `painel.seudominio.com`, `waha.seudominio.com`, `evolution.seudominio.com`)
- Acesso root/sudo via SSH

**Portas que precisam estar abertas no firewall**: 22 (SSH), 80, 443, 3001 (WAHA), 8080 (Evolution). Alternativamente, exponha só 80/443 e faça proxy reverso.

---

## 1. Instalação inicial

```bash
# atualize o sistema
sudo apt update && sudo apt upgrade -y

# docker + compose
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# nginx + certbot para HTTPS
sudo apt install -y nginx certbot python3-certbot-nginx git ufw

# firewall
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
```

---

## 2. Baixar o código

```bash
cd /opt
sudo git clone <URL_DO_SEU_REPO> zappedidos
sudo chown -R $USER:$USER zappedidos
cd zappedidos
```

Se você prefere baixar direto do Emergent, veja [`EXPORT.md`](EXPORT.md).

---

## 3. Configurar variáveis de ambiente

```bash
cp .env.example .env
nano .env
```

Edite pelo menos estes campos:

```env
# URL pública do painel (com https)
FRONTEND_URL=https://painel.seudominio.com

# Segredos — GERE VALORES ALEATÓRIOS FORTES
JWT_SECRET=<gere com: openssl rand -hex 32>
ADMIN_EMAIL=voce@seudominio.com
ADMIN_PASSWORD=<senha forte>

# WAHA
WAHA_DASHBOARD_USER=admin
WAHA_DASHBOARD_PASS=<senha forte>
WAHA_API_KEY=<gere com: openssl rand -hex 24>

# Evolution
EVOLUTION_URL=https://evolution.seudominio.com
EVOLUTION_API_KEY=<gere com: openssl rand -hex 24>
```

Adicione **também** no `backend/.env` (a chave de criptografia dos tokens Mercado Pago):

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copie o valor e coloque em `backend/.env`:

```env
TOKEN_ENCRYPTION_KEY=<valor gerado>
```

⚠️ **Nunca perca essa chave**: se for trocada, todos os tokens MP já cadastrados viram inválidos. Faça backup em cofre.

---

## 4. Subir a stack

```bash
docker compose up -d
docker compose ps      # todos "Up"
docker compose logs -f # acompanhar
```

Testes rápidos dentro da VPS:

```bash
curl http://localhost:8001/api/health          # backend
curl -I http://localhost                       # frontend
curl -I http://localhost:3001                  # WAHA
curl -I http://localhost:8080                  # Evolution
```

---

## 5. Nginx + HTTPS

Crie `/etc/nginx/sites-available/zappedidos.conf`:

```nginx
# Painel
server {
    listen 80;
    server_name painel.seudominio.com;

    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# WAHA Dashboard
server {
    listen 80;
    server_name waha.seudominio.com;
    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}

# Evolution
server {
    listen 80;
    server_name evolution.seudominio.com;
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Ative e gere certificados:

```bash
sudo ln -s /etc/nginx/sites-available/zappedidos.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo certbot --nginx \
  -d painel.seudominio.com \
  -d waha.seudominio.com \
  -d evolution.seudominio.com
```

Certbot cria renovação automática (`sudo certbot renew --dry-run`).

Atualize `FRONTEND_URL` no `.env` para a URL HTTPS final e faça `docker compose up -d --force-recreate frontend backend`.

---

## 6. Primeiro acesso

Abra `https://painel.seudominio.com` e entre com `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

1. **Crie uma loja** pela seção "Lojas e clientes".
2. **Configure WhatsApp** — escolha `WAHA` e informe `https://waha.seudominio.com` + a `WAHA_API_KEY` do `.env`.
3. Escaneie o QR code que aparece no painel.
4. **Configure LAD** — cole o Bearer token do lojista em Configurações.
5. **Configure Mercado Pago** — cole o Access Token nas Configurações e teste com o botão "Testar PIX de R$ 1,00".

---

## 7. Webhooks

No **WAHA Dashboard**, edite a sessão da loja e aponte o webhook para:
```
https://painel.seudominio.com/api/webhooks/whatsapp/<STORE_ID>
```

No **Mercado Pago → Suas integrações → Webhooks**, cole:
```
https://painel.seudominio.com/api/webhooks/mercadopago/<STORE_ID>
```
Selecione o tópico `payment`.

O `STORE_ID` aparece nas configurações da loja no painel (URL da tela ou copie do webhook mostrado).

---

## 8. Backup

Rode um cron diário:

```bash
sudo tee /etc/cron.daily/zappedidos-backup <<'EOF'
#!/bin/bash
set -e
DATE=$(date +%Y%m%d)
DEST=/var/backups/zappedidos
mkdir -p "$DEST"
docker exec zappedidos-mongo-1 mongodump --archive --gzip > "$DEST/mongo-$DATE.archive.gz"
tar -czf "$DEST/env-$DATE.tar.gz" /opt/zappedidos/.env /opt/zappedidos/backend/.env
find "$DEST" -type f -mtime +14 -delete
EOF
sudo chmod +x /etc/cron.daily/zappedidos-backup
```

---

## 9. Atualização (deploy contínuo)

```bash
cd /opt/zappedidos
git pull
docker compose build --pull
docker compose up -d
docker compose logs -f backend frontend
```

Se você modificar `TOKEN_ENCRYPTION_KEY` ou `JWT_SECRET`, os usuários precisarão logar de novo e tokens MP salvos serão perdidos — **evite trocar depois de tudo em produção**.

---

## 10. Troubleshooting

| Sintoma | Possível causa | Correção |
|---|---|---|
| 502 no painel | Container backend parou | `docker compose logs backend` e `docker compose restart backend` |
| CORS erro | `FRONTEND_URL` não bate | Confira `.env` e recrie o backend |
| QR não aparece | WAHA/Evolution não alcançável do backend | Verifique se URLs internas usam `http://waha:3000` (rede docker) ou URL externa; `docker compose logs waha` |
| Login "Sessão inválida" | Cookie sem `secure=True` em HTTP | Só funciona via HTTPS — configure nginx + certbot |
| PIX gera 401 | Access Token do MP inválido ou de outro ambiente | Reconfigure em Configurações → Mercado Pago |
| Webhook não grava conversa | URL errada ou HMAC incorreto | Confira URL no dashboard WAHA e nos logs `docker compose logs backend` |

---

Pronto! Você tem um ZapPedidos rodando em produção 🚀
