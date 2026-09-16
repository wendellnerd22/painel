import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, Bike, Clock, Copy, CreditCard, RefreshCw } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { brl, STATUS_LAD } from "@/lib/types";
import type { Cardapio, LojaInfo, Motoboy, OrderRecord, Route, Store } from "@/lib/types";
import AppShell from "@/components/layout/AppShell";
import { useMe } from "@/lib/session";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function StoreDetail() {
  const { id = "" } = useParams();
  const qc = useQueryClient();
  const me = useMe();

  const store = useQuery({ queryKey: ["store", id], queryFn: () => apiGet<Store>(`/stores/${id}`) });
  const loja = useQuery({
    queryKey: ["loja", id],
    queryFn: () => apiGet<LojaInfo>(`/stores/${id}/loja`),
    retry: false,
  });
  const cardapio = useQuery({
    queryKey: ["cardapio", id],
    queryFn: () => apiGet<Cardapio>(`/stores/${id}/cardapio`),
    retry: false,
  });
  const pedidos = useQuery({
    queryKey: ["pedidos", id],
    queryFn: () => apiGet<OrderRecord[]>(`/stores/${id}/pedidos`),
  });
  const rotas = useQuery({
    queryKey: ["rotas", id],
    queryFn: () => apiGet<Route[]>(`/rotas/${id}`),
  });
  const motoboys = useQuery({
    queryKey: ["motoboys", id],
    queryFn: () => apiGet<Motoboy[]>(`/motoboys/${id}`),
  });

  const [selecionados, setSelecionados] = useState<string[]>([]);
  const [motoboyId, setMotoboyId] = useState("");
  const [novoMotoboyNome, setNovoMotoboyNome] = useState("");
  const [novoMotoboyTelefone, setNovoMotoboyTelefone] = useState("");
  const [mostrarNovoMotoboy, setMostrarNovoMotoboy] = useState(false);

  const cadastrarMotoboy = useMutation({
    mutationFn: () =>
      apiPost<Motoboy>(`/motoboys/${id}`, {
        nome: novoMotoboyNome,
        telefone: novoMotoboyTelefone,
      }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: ["motoboys", id] });
      setNovoMotoboyNome("");
      setNovoMotoboyTelefone("");
      setMostrarNovoMotoboy(false);
      setMotoboyId(m.id);
      toast.success("Entregador cadastrado — instruções enviadas pelo WhatsApp");
    },
    onError: (err) => {
      const msg = err instanceof Error ? err.message : "Não foi possível cadastrar o entregador";
      toast.error(msg);
    },
  });

  const criarRota = useMutation({
    mutationFn: () =>
      apiPost<Route>(`/rotas/${id}`, {
        motoboy_id: motoboyId,
        pedido_ids: selecionados,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rotas", id] });
      qc.invalidateQueries({ queryKey: ["pedidos", id] });
      setSelecionados([]);
      setMotoboyId("");
      toast.success("Rota criada — motoboy e clientes avisados no WhatsApp");
    },
    onError: (err) => {
      const msg = err instanceof Error ? err.message : "Não foi possível criar a rota";
      toast.error(msg);
    },
  });

  const pedidosDisponiveis = (pedidos.data ?? []).filter((o) => !o.rota_id);

  function toggleSelecionado(pedidoId: string) {
    setSelecionados((cur) =>
      cur.includes(pedidoId) ? cur.filter((x) => x !== pedidoId) : [...cur, pedidoId]
    );
  }

  function copiarLink(url: string) {
    navigator.clipboard.writeText(url);
    toast.success("Link copiado");
  }

  const atualizar = useMutation({
    mutationFn: (uuid: string) => apiPost<OrderRecord>(`/stores/${id}/pedidos/${uuid}/atualizar`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pedidos", id] });
      toast.success("Status atualizado");
    },
    onError: () => toast.error("Não foi possível atualizar o pedido"),
  });

  const info = loja.isError ? undefined : loja.data;
  const menu = cardapio.isError ? undefined : cardapio.data;

  return (
    <AppShell>
      {me.data?.role === "admin" && (
        <Link
          to="/"
          className="mb-5 inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-primary"
          data-testid="back-to-stores-link"
        >
          <ArrowLeft className="size-4" /> Voltar para as lojas
        </Link>
      )}

      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold" data-testid="store-detail-title">
            {store.data?.nome ?? "Loja"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground" data-testid="store-detail-conexao">
            {store.data?.conexao_msg ?? "Carregando..."}
          </p>
        </div>
        <div className="flex gap-2">
          {info && (
            <Badge
              variant="outline"
              className={
                info.abertaAgora
                  ? "border-[#059669] bg-[#064E3B] text-[#A7F3D0]"
                  : "border-[#B91C1C] bg-[#3F1515] text-[#FEE2E2]"
              }
              data-testid="store-open-badge"
            >
              {info.abertaAgora ? "Aberta agora" : "Fechada"}
            </Badge>
          )}
          <Link
            to={`/simulador?loja=${id}`}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity duration-150 hover:opacity-90"
            data-testid="store-detail-simulator-link"
          >
            Testar bot
          </Link>
        </div>
      </div>

      <Tabs defaultValue="visao">
        <TabsList data-testid="store-tabs">
          <TabsTrigger value="visao" data-testid="tab-visao">Visão geral</TabsTrigger>
          <TabsTrigger value="cardapio" data-testid="tab-cardapio">Cardápio</TabsTrigger>
          <TabsTrigger value="pedidos" data-testid="tab-pedidos">Pedidos do bot</TabsTrigger>
          <TabsTrigger value="rotas" data-testid="tab-rotas">Rotas de entrega</TabsTrigger>
        </TabsList>

        <TabsContent value="visao" className="pt-6">
          {!info ? (
            <p className="text-sm text-muted-foreground" data-testid="loja-unavailable">
              Dados da loja indisponíveis. Verifique o token LAD ou ative o modo demonstração.
            </p>
          ) : (
            <div className="grid gap-6 md:grid-cols-3">
              <Card className="md:col-span-1">
                <CardContent className="space-y-3 py-5">
                  <h3 className="font-heading text-base font-bold">Dados</h3>
                  <Row label="Nome" value={info.nome} testid="info-nome" />
                  <Row label="Telefone" value={info.telefone ?? "-"} testid="info-telefone" />
                  <Row label="Endereço" value={info.endereco ?? "-"} testid="info-endereco" />
                  <Row label="Pedido mínimo" value={brl(info.pedidoMinimo)} testid="info-minimo" />
                  <Row
                    label="Modalidades"
                    value={[info.entregaDisponivel && "Entrega", info.retiradaDisponivel && "Retirada"]
                      .filter(Boolean)
                      .join(" · ")}
                    testid="info-modalidades"
                  />
                </CardContent>
              </Card>
              <Card>
                <CardContent className="space-y-2 py-5">
                  <h3 className="flex items-center gap-2 font-heading text-base font-bold">
                    <Clock className="size-4 text-primary" /> Horários
                  </h3>
                  <ul className="space-y-1 text-sm text-muted-foreground" data-testid="info-horarios">
                    {info.horarios.map((h) => (
                      <li key={`${h.diaDaSemana}-${h.abre}`} className="flex justify-between">
                        <span>{h.diaDaSemanaLabel}</span>
                        <span className="font-mono text-xs">{h.abre} – {h.fecha}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="space-y-3 py-5">
                  <h3 className="flex items-center gap-2 font-heading text-base font-bold">
                    <CreditCard className="size-4 text-primary" /> Formas de pagamento
                  </h3>
                  <div className="flex flex-wrap gap-2" data-testid="info-pagamentos">
                    {info.formasPagamento.map((f) => (
                      <Badge key={f} variant="secondary">{f}</Badge>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    O bot só usa exatamente estes rótulos ao criar o pedido.
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="cardapio" className="pt-6">
          {!menu ? (
            <p className="text-sm text-muted-foreground" data-testid="cardapio-unavailable">
              Cardápio indisponível no momento.
            </p>
          ) : (
            <div className="space-y-8" data-testid="cardapio-list">
              {menu.categorias.map((cat) => (
                <div key={cat.id}>
                  <h3 className="mb-3 font-heading text-lg font-bold">{cat.nome}</h3>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {cat.produtos.map((p) => (
                      <Card key={p.id} data-testid={`produto-card-${p.id}`}>
                        <CardContent className="space-y-2 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <span className="font-medium">{p.nome}</span>
                            <span className="whitespace-nowrap font-mono text-sm text-primary">
                              {brl(p.preco)}
                            </span>
                          </div>
                          {p.descricao && (
                            <p className="text-xs leading-relaxed text-muted-foreground">{p.descricao}</p>
                          )}
                          {p.tamanhos.length > 0 && (
                            <p className="text-xs text-muted-foreground">
                              Tamanhos: {p.tamanhos.map((t) => `${t.nome} ${brl(t.preco)}`).join(" · ")}
                            </p>
                          )}
                          {p.gruposOpcionais.length > 0 && (
                            <p className="text-xs text-muted-foreground">
                              Opcionais: {p.gruposOpcionais.map((g) => g.nome).join(", ")}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="pedidos" className="pt-6">
          {(pedidos.data ?? []).length === 0 ? (
            <p className="text-sm text-muted-foreground" data-testid="pedidos-empty">
              Nenhum pedido criado pelo bot ainda.
            </p>
          ) : (
            <Table data-testid="pedidos-table">
              <TableHeader>
                <TableRow>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Total</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(pedidos.data ?? []).map((o) => {
                  const st = STATUS_LAD[o.status_codigo] ?? {
                    label: o.status_descricao,
                    className: "bg-secondary text-foreground border-border",
                  };
                  return (
                    <TableRow key={o.id} data-testid={`pedido-row-${o.id}`}>
                      <TableCell>
                        <span className="font-medium">{o.cliente_nome || "—"}</span>
                        <span className="block font-mono text-[11px] text-muted-foreground">
                          {o.id.slice(0, 8)}
                        </span>
                      </TableCell>
                      <TableCell>{o.tipo}</TableCell>
                      <TableCell className="font-mono">{brl(o.valor_total)}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={st.className}>{st.label}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="xs"
                          onClick={() => atualizar.mutate(o.id)}
                          data-testid={`pedido-refresh-${o.id}`}
                        >
                          <RefreshCw className="size-3" /> Atualizar
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </TabsContent>

        <TabsContent value="rotas" className="pt-6 space-y-6">
          <Card>
            <CardContent className="space-y-4 py-5">
              <h3 className="flex items-center gap-2 font-heading text-base font-bold">
                <Bike className="size-4 text-primary" /> Montar rota
              </h3>
              <p className="text-xs text-muted-foreground">
                Selecione os pedidos já expedidos, informe o motoboy e crie a rota — cada cliente
                selecionado recebe automaticamente o link de rastreamento ao vivo no WhatsApp.
              </p>

              {pedidosDisponiveis.length === 0 ? (
                <p className="text-sm text-muted-foreground" data-testid="rota-sem-pedidos">
                  Nenhum pedido disponível pra colocar em rota no momento.
                </p>
              ) : (
                <div className="rounded-lg border border-border" data-testid="rota-pedidos-lista">
                  {pedidosDisponiveis.map((o) => (
                    <label
                      key={o.id}
                      className="flex cursor-pointer items-center gap-3 border-b border-border px-3 py-2 text-sm last:border-b-0"
                      data-testid={`rota-pedido-${o.id}`}
                    >
                      <Checkbox
                        checked={selecionados.includes(o.id)}
                        onCheckedChange={() => toggleSelecionado(o.id)}
                      />
                      <span className="flex-1">
                        <span className="font-medium">{o.cliente_nome || "Cliente"}</span>
                        <span className="ml-2 font-mono text-[11px] text-muted-foreground">
                          {o.id.slice(0, 8)}
                        </span>
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">{brl(o.valor_total)}</span>
                    </label>
                  ))}
                </div>
              )}

              <div className="space-y-3">
                <Label>Motoboy</Label>
                <div className="flex flex-wrap items-center gap-2">
                  <Select value={motoboyId} onValueChange={setMotoboyId}>
                    <SelectTrigger className="w-60" data-testid="motoboy-select">
                      <SelectValue placeholder="Escolha o entregador">
                        {(v) => motoboys.data?.find((m) => m.id === v)?.nome ?? "Escolha o entregador"}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {(motoboys.data ?? []).map((m) => (
                        <SelectItem key={m.id} value={m.id} data-testid={`motoboy-option-${m.id}`}>
                          {m.nome} · {m.telefone}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setMostrarNovoMotoboy((v) => !v)}
                    data-testid="novo-motoboy-toggle"
                  >
                    + Novo entregador
                  </Button>
                </div>

                {mostrarNovoMotoboy && (
                  <div className="grid gap-3 rounded-lg border border-border bg-secondary/40 p-3 sm:grid-cols-[1fr_1fr_auto]">
                    <div className="space-y-1.5">
                      <Label htmlFor="novo-motoboy-nome">Nome</Label>
                      <Input
                        id="novo-motoboy-nome"
                        value={novoMotoboyNome}
                        onChange={(e) => setNovoMotoboyNome(e.target.value)}
                        placeholder="Ex.: Carlos"
                        data-testid="novo-motoboy-nome-input"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="novo-motoboy-telefone">Telefone (WhatsApp)</Label>
                      <Input
                        id="novo-motoboy-telefone"
                        value={novoMotoboyTelefone}
                        onChange={(e) => setNovoMotoboyTelefone(e.target.value)}
                        placeholder="Ex.: 5511999998888"
                        data-testid="novo-motoboy-telefone-input"
                      />
                    </div>
                    <div className="flex items-end">
                      <Button
                        type="button"
                        onClick={() => cadastrarMotoboy.mutate()}
                        disabled={
                          !novoMotoboyNome.trim() || !novoMotoboyTelefone.trim() || cadastrarMotoboy.isPending
                        }
                        data-testid="cadastrar-motoboy-btn"
                      >
                        {cadastrarMotoboy.isPending ? "Cadastrando..." : "Cadastrar"}
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              <Button
                onClick={() => criarRota.mutate()}
                disabled={selecionados.length === 0 || !motoboyId || criarRota.isPending}
                data-testid="criar-rota-btn"
              >
                <Bike className="size-4" />
                {criarRota.isPending ? "Criando rota..." : `Criar rota com ${selecionados.length} pedido(s)`}
              </Button>
            </CardContent>
          </Card>

          <div>
            <h3 className="mb-3 font-heading text-base font-bold">Rotas criadas</h3>
            {(rotas.data ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground" data-testid="rotas-empty">
                Nenhuma rota criada ainda.
              </p>
            ) : (
              <div className="space-y-3" data-testid="rotas-lista">
                {(rotas.data ?? []).map((r) => (
                  <Card key={r.id} data-testid={`rota-card-${r.id}`}>
                    <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                      <div>
                        <p className="font-medium">{r.motoboy_nome}</p>
                        <p className="text-xs text-muted-foreground">
                          {r.pedido_ids.length} pedido(s) · criada em{" "}
                          {new Date(r.created_at).toLocaleString("pt-BR")}
                        </p>
                      </div>
                      {r.tracking_url && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copiarLink(r.tracking_url!)}
                          data-testid={`rota-copiar-link-${r.id}`}
                        >
                          <Copy className="size-3.5" /> Copiar link de rastreamento
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </AppShell>
  );
}

function Row({ label, value, testid }: { label: string; value: string; testid: string }) {
  return (
    <div className="flex items-start justify-between gap-4 text-sm" data-testid={testid}>
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}
