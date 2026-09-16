import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, Copy, ExternalLink, RefreshCw, ShieldCheck } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { brl, STATUS_PAGAMENTO } from "@/lib/types";
import type { PaymentIntent } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface Props {
  intentId: string;
  onApproved?: () => void;
}

export default function PaymentPanel({ intentId, onApproved }: Props) {
  const qc = useQueryClient();
  const intent = useQuery({
    queryKey: ["payment", intentId],
    queryFn: () => apiGet<PaymentIntent>(`/payments/${intentId}`),
    refetchInterval: (q) => (q.state.data?.status === "pendente" ? 10_000 : false),
    retry: false,
  });

  const verificar = useMutation({
    mutationFn: () => apiPost<PaymentIntent>(`/payments/${intentId}/verificar`),
    onSuccess: (data) => {
      qc.setQueryData(["payment", intentId], data);
      if (data.status === "aprovado") onApproved?.();
      else toast.info("Pagamento ainda não confirmado");
    },
  });

  const simular = useMutation({
    mutationFn: () => apiPost<PaymentIntent>(`/payments/${intentId}/simular-aprovacao`),
    onSuccess: (data) => {
      qc.setQueryData(["payment", intentId], data);
      qc.invalidateQueries({ queryKey: ["pedidos", data.store_id] });
      qc.invalidateQueries({ queryKey: ["pagamentos", data.store_id] });
      toast.success("Pagamento aprovado (simulado)", {
        description: data.lad_order_uuid ? "Pedido enviado à loja" : data.lad_erro ?? undefined,
      });
      onApproved?.();
    },
    onError: () => toast.error("Não foi possível simular o pagamento"),
  });

  const data = intent.data;
  const st = data ? STATUS_PAGAMENTO[data.status] ?? STATUS_PAGAMENTO.pendente : null;

  return (
    <Card data-testid="payment-panel">
      <CardContent className="space-y-4 py-5">
        <div className="flex items-center justify-between gap-3">
          <h3 className="flex items-center gap-2 font-heading text-base font-bold">
            <ShieldCheck className="size-4 text-primary" /> Pagamento antecipado
          </h3>
          {st && (
            <Badge variant="outline" className={st.className} data-testid="payment-status-badge">
              {st.label}
            </Badge>
          )}
        </div>

        {!data ? (
          <p className="text-xs text-muted-foreground" data-testid="payment-loading">
            Carregando cobrança...
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                  Total a pagar
                </p>
                <p className="font-heading text-2xl font-bold" data-testid="payment-amount">
                  {brl(data.valor)}
                </p>
              </div>
              <p className="text-xs text-muted-foreground">
                {data.metodo === "pix" ? "PIX" : "Cartão"} · itens {brl(data.valor_itens)} + entrega{" "}
                {brl(data.valor_entrega)}
              </p>
            </div>

            {data.pix_qr_base64 ? (
              <img
                src={`data:image/png;base64,${data.pix_qr_base64}`}
                alt="QR Code PIX"
                className="size-44 rounded-xl border border-border bg-white p-2"
                data-testid="payment-qr-image"
              />
            ) : null}

            {data.pix_copia_e_cola ? (
              <div className="space-y-2">
                <code
                  className="block break-all rounded-lg border border-border bg-secondary/40 px-3 py-2 font-mono text-[11px]"
                  data-testid="payment-pix-code"
                >
                  {data.pix_copia_e_cola}
                </code>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(data.pix_copia_e_cola).catch(() => undefined);
                    toast.success("Código PIX copiado");
                  }}
                  data-testid="payment-copy-pix-button"
                >
                  <Copy className="size-4" /> Copiar código PIX
                </Button>
              </div>
            ) : null}

            {data.checkout_url && data.metodo === "cartao" ? (
              <a
                href={data.checkout_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity duration-150 hover:opacity-90"
                data-testid="payment-checkout-link"
              >
                Abrir link de pagamento <ExternalLink className="size-4" />
              </a>
            ) : null}

            {data.lad_order_uuid ? (
              <p className="flex items-center gap-2 text-sm text-primary" data-testid="payment-order-created">
                <CheckCircle2 className="size-4" /> Pedido enviado à loja ·{" "}
                <span className="font-mono text-xs">{data.lad_order_uuid.slice(0, 8)}</span>
              </p>
            ) : null}
            {data.lad_erro ? (
              <p className="text-sm text-destructive" data-testid="payment-lad-error">
                A loja recusou o pedido: {data.lad_erro}
              </p>
            ) : null}

            <div className="flex flex-wrap gap-2 pt-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => verificar.mutate()}
                disabled={verificar.isPending}
                data-testid="payment-verify-button"
              >
                <RefreshCw className="size-4" /> Já paguei / verificar
              </Button>
              {data.provider === "simulado" && data.status === "pendente" ? (
                <Button size="sm" onClick={() => simular.mutate()} disabled={simular.isPending}
                        data-testid="payment-simulate-button">
                  Simular pagamento aprovado
                </Button>
              ) : null}
            </div>
            {data.provider === "simulado" ? (
              <p className="text-xs text-muted-foreground" data-testid="payment-simulated-note">
                Modo simulado: sem chaves do Mercado Pago no .env, o código PIX é fictício e a
                aprovação é manual. Com as chaves, a confirmação vem por webhook e polling.
              </p>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
