import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  MessageSquare,
  Plus,
  RefreshCw,
  Store as StoreIcon,
  Trash2,
} from "lucide-react";
import { apiDelete, apiGet, apiPost } from "@/lib/api";
import type { ConnectionResult, Store } from "@/lib/types";
import AppShell from "@/components/layout/AppShell";
import StoreFormDialog from "@/components/stores/StoreFormDialog";
import { useMe } from "@/lib/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function Home() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const me = useMe();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Store | null>(null);

  useEffect(() => {
    if (me.data && me.data.role !== "admin") {
      navigate(`/lojas/${me.data.store_id ?? ""}`, { replace: true });
    }
  }, [me.data, navigate]);

  const { data: stores, isError } = useQuery({
    queryKey: ["stores"],
    queryFn: () => apiGet<Store[]>("/stores"),
  });

  const testar = useMutation({
    mutationFn: (id: string) => apiPost<ConnectionResult>(`/stores/${id}/testar`),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["stores"] });
      if (res.ok) toast.success(res.mensagem, { description: res.nome_loja ?? undefined });
      else toast.error("Falha na conexão", { description: res.mensagem });
    },
    onError: () => toast.error("Não foi possível testar a conexão"),
  });

  const remover = useMutation({
    mutationFn: (id: string) => apiDelete<void>(`/stores/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["stores"] });
      toast.success("Loja removida");
    },
  });

  const list = stores ?? [];
  const conectadas = list.filter((s) => s.conexao_ok).length;

  return (
    <AppShell>
      <section className="relative mb-10 overflow-hidden rounded-3xl border border-border bg-card px-7 py-10">
        <div className="pointer-events-none absolute -right-24 -top-28 size-80 rounded-full bg-primary/15 blur-3xl" />
        <div className="relative max-w-2xl">
          <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
            Automação de WhatsApp para delivery
          </span>
          <h1 className="mt-3 text-4xl font-extrabold leading-[1.05] md:text-5xl" data-testid="hero-title">
            Um atendente de IA por loja,
            <span className="block text-primary">pedidos direto na LAD.</span>
          </h1>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-muted-foreground">
            Cadastre o token LAD de cada cliente, deixe o bot conversar, montar o carrinho e enviar o
            pedido pela API v1 — com preços oficiais calculados pelo servidor e chave de idempotência.
          </p>
          <div className="mt-7 flex flex-wrap gap-3">
            <Button
              onClick={() => {
                setEditing(null);
                setDialogOpen(true);
              }}
              data-testid="add-store-button"
            >
              <Plus className="size-4" /> Cadastrar loja
            </Button>
            <Link
              to="/simulador"
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-foreground transition-colors duration-150 hover:border-primary/60 hover:text-primary"
              data-testid="hero-simulator-link"
            >
              <MessageSquare className="size-4" /> Abrir simulador
            </Link>
          </div>
        </div>
        <div className="relative mt-9 flex flex-wrap gap-8 border-t border-border/70 pt-6">
          <Stat label="Lojas cadastradas" value={String(list.length)} testid="stat-lojas" />
          <Stat label="Conexões OK" value={String(conectadas)} testid="stat-conectadas" />
          <Stat label="Modelo do bot" value="Gemini 3 Flash" testid="stat-modelo" />
        </div>
      </section>

      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-bold">Suas lojas</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setEditing(null);
            setDialogOpen(true);
          }}
          data-testid="add-store-button-secondary"
        >
          <Plus className="size-4" /> Nova loja
        </Button>
      </div>

      {isError && (
        <p className="mb-4 text-sm text-destructive" data-testid="stores-error">
          Não foi possível carregar as lojas agora.
        </p>
      )}

      {list.length === 0 ? (
        <Card className="border-dashed" data-testid="stores-empty">
          <CardContent className="flex flex-col items-start gap-3 py-10">
            <StoreIcon className="size-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Nenhuma loja ainda. Cadastre a primeira — sem token ela roda em modo demonstração.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {list.map((store, i) => (
            <motion.div
              key={store.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: i * 0.04 }}
            >
              <Card
                className="h-full border-border transition-[transform,border-color] duration-200 hover:-translate-y-1 hover:border-primary/50"
                data-testid={`store-card-${store.id}`}
              >
                <CardContent className="flex h-full flex-col gap-4 py-5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <Link
                        to={`/lojas/${store.id}`}
                        className="font-heading text-lg font-bold hover:text-primary"
                        data-testid={`store-name-link-${store.id}`}
                      >
                        {store.nome}
                      </Link>
                      <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                        {store.demo || !store.token ? "MODO DEMO" : `TOKEN ****${store.token.slice(-6)}`}
                      </p>
                    </div>
                    <Badge
                      variant="outline"
                      className={
                        store.conexao_ok
                          ? "border-[#059669] bg-[#064E3B] text-[#A7F3D0]"
                          : "border-[#B91C1C] bg-[#3F1515] text-[#FEE2E2]"
                      }
                      data-testid={`store-status-${store.id}`}
                    >
                      {store.conexao_ok ? (
                        <CheckCircle2 className="size-3" />
                      ) : (
                        <AlertTriangle className="size-3" />
                      )}
                      {store.conexao_ok ? "Conectada" : "Erro"}
                    </Badge>
                  </div>
                  <p className="text-xs leading-relaxed text-muted-foreground" data-testid={`store-msg-${store.id}`}>
                    {store.conexao_msg}
                  </p>
                  <div className="mt-auto flex flex-wrap gap-2 pt-2">
                    <Link
                      to={`/lojas/${store.id}`}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs transition-colors duration-150 hover:border-primary/60 hover:text-primary"
                      data-testid={`store-open-link-${store.id}`}
                    >
                      Abrir
                    </Link>
                    <Link
                      to={`/simulador?loja=${store.id}`}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs transition-colors duration-150 hover:border-primary/60 hover:text-primary"
                      data-testid={`store-chat-link-${store.id}`}
                    >
                      Testar bot
                    </Link>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => testar.mutate(store.id)}
                      data-testid={`store-test-button-${store.id}`}
                    >
                      <RefreshCw className="size-3" /> Testar
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => {
                        setEditing(store);
                        setDialogOpen(true);
                      }}
                      data-testid={`store-edit-button-${store.id}`}
                    >
                      Editar
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      className="text-destructive"
                      onClick={() => remover.mutate(store.id)}
                      data-testid={`store-delete-button-${store.id}`}
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      <StoreFormDialog open={dialogOpen} onOpenChange={setDialogOpen} store={editing} />
    </AppShell>
  );
}

function Stat({ label, value, testid }: { label: string; value: string; testid: string }) {
  return (
    <div data-testid={testid}>
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-2xl font-bold">{value}</p>
    </div>
  );
}
