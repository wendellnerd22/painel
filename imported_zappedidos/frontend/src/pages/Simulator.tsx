import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { toast } from "sonner";
import { CheckCircle2, RotateCcw, Send, XCircle } from "lucide-react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import type { ChatMessage, ChatResponse, Store, ToolTrace } from "@/lib/types";
import AppShell from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const SESSION_KEY = "lad-sim-session";

function getSession(): string {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const fresh = `sim-${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem(SESSION_KEY, fresh);
  return fresh;
}

const SUGESTOES = [
  "Oi, boa noite! O que vocês têm hoje?",
  "Quero um X-Salada com bacon extra",
  "Pode ser entrega na Rua Natal, 123, Centro, Porto Alegre",
];

export default function Simulator() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [text, setText] = useState("");
  const [session] = useState(getSession);
  const [pending, setPending] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const stores = useQuery({ queryKey: ["stores"], queryFn: () => apiGet<Store[]>("/stores") });
  const list = useMemo(() => stores.data ?? [], [stores.data]);
  const storeId = params.get("loja") ?? list[0]?.id ?? "";

  useEffect(() => {
    if (!params.get("loja") && list[0]) setParams({ loja: list[0].id }, { replace: true });
  }, [list, params, setParams]);

  const history = useQuery({
    queryKey: ["chat", storeId, session],
    queryFn: () => apiGet<ChatMessage[]>(`/chat/${storeId}/${session}`),
    enabled: Boolean(storeId),
  });

  const send = useMutation({
    mutationFn: (message: string) =>
      apiPost<ChatResponse>(`/chat/${storeId}`, { session_id: session, message }),
    onSettled: () => setPending(null),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["chat", storeId, session] });
      qc.invalidateQueries({ queryKey: ["pedidos", storeId] });
      // Linha corrigida (desativada) abaixo:
      // if (res.payment_intent_id) setIntentId(res.payment_intent_id);
      if (res.order_uuid) toast.success("Pedido criado na LAD", { description: res.order_uuid });
    },
    onError: () => toast.error("O bot não conseguiu responder. Tente novamente."),
  });

  const reset = useMutation({
    mutationFn: () => apiDelete<void>(`/chat/${storeId}/${session}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat", storeId, session] });
      toast.success("Conversa reiniciada");
    },
  });

  const messages = history.data ?? [];
  const traces: ToolTrace[] = messages.flatMap((m) => m.tools);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, send.isPending]);

  const submit = () => {
    const value = text.trim();
    if (!value || !storeId || send.isPending) return;
    setText("");
    setPending(value);
    send.mutate(value);
  };

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold" data-testid="simulator-title">Simulador de chat</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Converse como se fosse o cliente no WhatsApp. O bot usa as ferramentas da API LAD v1.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={storeId}
            onValueChange={(v: string) => setParams({ loja: v })}
          >
            <SelectTrigger className="w-60" data-testid="simulator-store-select">
              <SelectValue placeholder="Escolha a loja">
                {(v) => list.find((s) => s.id === v)?.nome ?? "Escolha a loja"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {list.map((s) => (
                <SelectItem key={s.id} value={s.id} data-testid={`simulator-store-option-${s.id}`}>
                  {s.nome}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={() => reset.mutate()}
            disabled={!storeId}
            data-testid="simulator-reset-button"
          >
            <RotateCcw className="size-4" /> Reiniciar
          </Button>
        </div>
      </div>

      {list.length === 0 && (
        <p className="mb-6 text-sm text-muted-foreground" data-testid="simulator-no-store">
          Cadastre uma loja primeiro para conversar com o bot.
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="overflow-hidden rounded-3xl border border-border shadow-[0_20px_60px_rgba(0,0,0,0.45)]">
          <div className="flex items-center gap-3 bg-[#111b21] px-4 py-3">
            <span className="grid size-9 place-items-center rounded-full bg-primary/20 font-heading text-sm font-bold text-primary">
              {(list.find((s) => s.id === storeId)?.nome ?? "?").slice(0, 1)}
            </span>
            <div className="leading-tight">
              <p className="text-sm font-medium" data-testid="chat-header-store">
                {list.find((s) => s.id === storeId)?.nome ?? "Selecione uma loja"}
              </p>
              <p className="text-[11px] text-muted-foreground">atendimento automático</p>
            </div>
          </div>

          <div className="lad-chat-bg h-[460px] space-y-3 overflow-y-auto p-4" data-testid="chat-messages">
            {messages.length === 0 && (
              <p className="mx-auto mt-16 max-w-[260px] text-center text-xs text-muted-foreground">
                Envie a primeira mensagem para começar o atendimento.
              </p>
            )}
            {messages.map((m) => (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
              >
                <div
                  data-testid={`chat-bubble-${m.role}-${m.id}`}
                  className={
                    m.role === "user"
                      ? "max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-[#005c4b] px-3 py-2 text-sm text-[#e9edef]"
                      : "max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-[#202c33] px-3 py-2 text-sm text-[#e9edef]"
                  }
                >
                  {m.text}
                </div>
              </motion.div>
            ))}
            {send.isPending && pending && (
              <div className="flex justify-end" data-testid="chat-bubble-pending">
                <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-[#005c4b]/70 px-3 py-2 text-sm text-[#e9edef]">
                  {pending}
                </div>
              </div>
            )}
            {send.isPending && (
              <div className="flex justify-start" data-testid="chat-typing-indicator">
                <div className="flex gap-1 rounded-2xl rounded-bl-sm bg-[#202c33] px-4 py-3">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="lad-typing-dot size-1.5 rounded-full bg-[#8696a0]"
                      style={{ animationDelay: `${i * 0.18}s` }}
                    />
                  ))}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div className="flex items-center gap-2 border-t border-border bg-[#111b21] p-3">
            <Input
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") submit();
              }}
              placeholder="Mensagem"
              disabled={!storeId}
              data-testid="chat-input"
              className="border-none bg-[#2a3942]"
            />
            <Button
              size="icon"
              onClick={submit}
              disabled={!storeId || send.isPending || !text.trim()}
              data-testid="chat-send-button"
            >
              <Send className="size-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          <Card>
            <CardContent className="space-y-3 py-5">
              <h3 className="font-heading text-base font-bold">Sugestões rápidas</h3>
              <div className="flex flex-wrap gap-2">
                {SUGESTOES.map((s, i) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setText(s)}
                    data-testid={`chat-suggestion-${i}`}
                    className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors duration-150 hover:border-primary/60 hover:text-primary"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-3 py-5">
              <h3 className="font-heading text-base font-bold">Chamadas à API LAD</h3>
              {traces.length === 0 ? (
                <p className="text-xs text-muted-foreground" data-testid="tool-trace-empty">
                  Nenhuma ferramenta executada ainda.
                </p>
              ) : (
                <ul className="space-y-2" data-testid="tool-trace-list">
                  {traces.map((t, i) => (
                    <li
                      key={`${t.name}-${i}`}
                      data-testid={`tool-trace-${i}`}
                      className="flex items-start gap-2 rounded-lg border border-border bg-secondary/40 px-3 py-2 text-xs"
                    >
                      {t.ok ? (
                        <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-primary" />
                      ) : (
                        <XCircle className="mt-0.5 size-3.5 shrink-0 text-destructive" />
                      )}
                      <span>
                        <span className="font-mono text-[11px] uppercase tracking-wider text-foreground">
                          {t.name}
                        </span>
                        <span className="block text-muted-foreground">{t.resumo}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}