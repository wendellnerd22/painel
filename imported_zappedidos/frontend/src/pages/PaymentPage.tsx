import { useParams } from "react-router-dom";
import { Zap } from "lucide-react";
import PaymentPanel from "@/components/payments/PaymentPanel";

/** Página pública: é o link que o cliente recebe no WhatsApp para pagar e acompanhar. */
export default function PaymentPage() {
  const { id = "" } = useParams();
  return (
    <div className="min-h-screen bg-background px-5 py-12">
      <div className="mx-auto max-w-lg">
        <div className="mb-7 flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl bg-primary/15 ring-1 ring-primary/40">
            <Zap className="size-4 text-primary" />
          </span>
          <span className="font-heading text-base font-bold">ZapPedidos</span>
        </div>
        <h1 className="text-2xl font-extrabold" data-testid="payment-page-title">
          Pagamento do seu pedido
        </h1>
        <p className="mb-6 mt-1 text-sm text-muted-foreground">
          O pedido é enviado à loja assim que o pagamento for confirmado.
        </p>
        <PaymentPanel intentId={id} />
      </div>
    </div>
  );
}
