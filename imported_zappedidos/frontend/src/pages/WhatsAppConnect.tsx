import { Link } from "react-router-dom";
import { Copy, ExternalLink, Server, Smartphone, Terminal } from "lucide-react";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

const WEBHOOK_SNIPPET = `# Baileys (Node, MIT) — encaminha cada mensagem para este painel
import makeWASocket, { useMultiFileAuthState } from '@whiskeysockets/baileys'

const { state, saveCreds } = await useMultiFileAuthState('auth')
const sock = makeWASocket({ auth: state, printQRInTerminal: true })
sock.ev.on('creds.update', saveCreds)

sock.ev.on('messages.upsert', async ({ messages }) => {
  const msg = messages[0]
  if (!msg.message || msg.key.fromMe) return
  const texto = msg.message.conversation ?? ''
  const r = await fetch('SEU_PAINEL/api/chat/ID_DA_LOJA', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': 'CHAVE_DA_LOJA' },
    body: JSON.stringify({ session_id: msg.key.remoteJid, message: texto }),
  })
  const { reply } = await r.json()
  await sock.sendMessage(msg.key.remoteJid, { text: reply })
})`;

const OPTIONS = [
  {
    nome: "Baileys",
    licenca: "MIT",
    descricao:
      "Biblioteca Node.js que fala o protocolo do WhatsApp Web direto por WebSocket. Sem navegador, sem custo por mensagem — conecta lendo o QR Code.",
    url: "https://github.com/WhiskeySockets/Baileys",
  },
  {
    nome: "Evolution API",
    licenca: "Apache 2.0",
    descricao:
      "API REST self-hosted em cima do Baileys, com painel, multi-instância e webhooks prontos. É a opção mais rápida para revenda multi-loja.",
    url: "https://github.com/EvolutionAPI/evolution-api",
  },
  {
    nome: "WPPConnect",
    licenca: "Apache 2.0",
    descricao:
      "Projeto brasileiro maduro com servidor REST próprio (wppconnect-server) e boa documentação em português.",
    url: "https://github.com/wppconnect-team/wppconnect",
  },
];

export default function WhatsAppConnect() {
  const copy = () => {
    navigator.clipboard.writeText(WEBHOOK_SNIPPET).catch(() => undefined);
    toast.success("Código copiado");
  };

  return (
    <AppShell>
      <div className="mb-8 max-w-3xl">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">Conexão</span>
        <h1 className="mt-2 text-3xl font-extrabold" data-testid="whatsapp-title">
          Ligue o bot a um número de WhatsApp
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          O cérebro do atendimento já está pronto neste painel: um único endpoint recebe a mensagem do
          cliente e devolve a resposta do bot. Basta um conector open source encaminhar as mensagens.
        </p>
        <Badge variant="outline" className="mt-4 border-[#D97706] bg-[#3B2505] text-[#FDE68A]" data-testid="whatsapp-status-badge">
          Nenhum número conectado
        </Badge>
      </div>

      <div className="mb-10 grid gap-6 md:grid-cols-3">
        {OPTIONS.map((o) => (
          <Card key={o.nome} className="transition-[border-color] duration-200 hover:border-primary/50">
            <CardContent className="space-y-3 py-5" data-testid={`whatsapp-option-${o.nome.toLowerCase().replace(/\s/g, "-")}`}>
              <div className="flex items-center justify-between">
                <h3 className="font-heading text-lg font-bold">{o.nome}</h3>
                <Badge variant="secondary">{o.licenca}</Badge>
              </div>
              <p className="text-xs leading-relaxed text-muted-foreground">{o.descricao}</p>
              <a
                href={o.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
              >
                Ver no GitHub <ExternalLink className="size-3" />
              </a>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardContent className="space-y-4 py-5">
            <h2 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Terminal className="size-4 text-primary" /> Exemplo de conector
            </h2>
            <pre className="max-h-[380px] overflow-auto rounded-xl border border-border bg-[#0d141c] p-4 font-mono text-[11px] leading-relaxed text-[#cbd5e1]" data-testid="whatsapp-snippet">
              {WEBHOOK_SNIPPET}
            </pre>
            <Button variant="outline" size="sm" onClick={copy} data-testid="whatsapp-copy-button">
              <Copy className="size-4" /> Copiar código
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-4 py-5">
            <h2 className="flex items-center gap-2 font-heading text-lg font-bold">
              <Server className="size-4 text-primary" /> Como funciona
            </h2>
            <ol className="space-y-3 text-sm text-muted-foreground" data-testid="whatsapp-steps">
              {[
                "Cadastre a loja aqui e teste o bot no simulador.",
                "Suba o conector open source no seu servidor (Docker resolve).",
                "Leia o QR Code com o WhatsApp do lojista.",
                "Aponte o webhook para POST /api/chat/{id_da_loja} deste painel, com o header X-API-Key da loja (veja em Editar loja).",
                "Devolva o campo reply ao cliente — o pedido já entra na LAD.",
              ].map((s, i) => (
                <li key={s} className="flex gap-3">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/15 font-mono text-[11px] text-primary">
                    {i + 1}
                  </span>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
            <div className="rounded-xl border border-border bg-secondary/40 p-3 text-xs text-muted-foreground">
              <Smartphone className="mb-2 size-4 text-primary" />
              Use o <code className="font-mono">session_id</code> igual ao número do cliente para que
              cada conversa mantenha o próprio carrinho.
            </div>
            <Link
              to="/simulador"
              className="inline-flex text-sm text-primary hover:underline"
              data-testid="whatsapp-simulator-link"
            >
              Testar no simulador primeiro
            </Link>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
