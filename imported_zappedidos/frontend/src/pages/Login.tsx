import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { Zap } from "lucide-react";
import { apiPost } from "@/lib/api";
import { beginSession } from "@/lib/session";
import type { SessionUser } from "@/lib/session";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");

  const login = useMutation({
    mutationFn: () => apiPost<SessionUser>("/auth/login", { email: email.trim().toLowerCase(), senha }),
    onSuccess: async (user) => {
      await beginSession();
      toast.success(`Bem-vindo, ${user.nome || user.email}`);
      navigate(user.role === "admin" ? "/" : `/lojas/${user.store_id ?? ""}`, { replace: true });
    },
    onError: () => toast.error("E-mail ou senha inválidos"),
  });

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-border bg-card p-12 lg:flex">
        <div className="pointer-events-none absolute -left-20 top-1/3 size-96 rounded-full bg-primary/12 blur-3xl" />
        <div className="relative flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl bg-primary/15 ring-1 ring-primary/40">
            <Zap className="size-4 text-primary" />
          </span>
          <span className="font-heading text-base font-bold">ZapPedidos</span>
        </div>
        <div className="relative max-w-md">
          <h2 className="text-4xl font-extrabold leading-tight">
            Atendimento automático,
            <span className="block text-primary">pedidos na LAD.</span>
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
            O revendedor administra todas as lojas. Cada lojista entra e vê apenas a própria loja,
            seus pedidos e o simulador do bot.
          </p>
        </div>
        <p className="relative font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          LAD Delivery API v1
        </p>
      </div>

      <div className="flex items-center justify-center p-6">
        <Card className="w-full max-w-sm">
          <CardContent className="space-y-5 py-7">
            <div>
              <h1 className="text-2xl font-bold" data-testid="login-title">Entrar no painel</h1>
              <p className="mt-1 text-sm text-muted-foreground">Use o e-mail e a senha do seu acesso.</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="login-email">E-mail</Label>
              <Input
                id="login-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email-input"
                placeholder="voce@empresa.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="login-senha">Senha</Label>
              <Input
                id="login-senha"
                type="password"
                autoComplete="current-password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && email && senha) login.mutate();
                }}
                data-testid="login-senha-input"
                placeholder="••••••••"
              />
            </div>
            <Button
              className="w-full"
              onClick={() => login.mutate()}
              disabled={!email.trim() || !senha || login.isPending}
              data-testid="login-submit-button"
            >
              {login.isPending ? "Entrando..." : "Entrar"}
            </Button>
            <p className="text-xs leading-relaxed text-muted-foreground" data-testid="login-hint">
              Acesso do revendedor criado nesta instalação:
              <span className="mt-1 block font-mono text-[11px] text-foreground">
                admin@zappedidos.com · Zap@2026
              </span>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
