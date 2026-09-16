import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import { LayoutGrid, LogOut, MessageSquare, Smartphone, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { endSession, useMe } from "@/lib/session";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/", label: "Lojas", icon: LayoutGrid, testid: "nav-lojas", adminOnly: true },
  { to: "/simulador", label: "Simulador de Chat", icon: MessageSquare, testid: "nav-simulador", adminOnly: false },
  { to: "/whatsapp", label: "Conexão WhatsApp", icon: Smartphone, testid: "nav-whatsapp", adminOnly: true },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const me = useMe();

  useEffect(() => {
    if (me.isError) navigate("/login", { replace: true });
  }, [me.isError, navigate]);

  const user = me.data;
  const items = NAV.filter((i) => !i.adminOnly || user?.role === "admin");

  const sair = async () => {
    await endSession();
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header
        className="sticky top-0 z-40 border-b border-border/80 bg-background/70 backdrop-blur-xl"
        data-testid="app-header"
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-5">
          <Link
            to={user?.role === "admin" ? "/" : `/lojas/${user?.store_id ?? ""}`}
            className="flex items-center gap-2.5"
            data-testid="brand-link"
          >
            <span className="grid size-9 place-items-center rounded-xl bg-primary/15 ring-1 ring-primary/40">
              <Zap className="size-4 text-primary" />
            </span>
            <span className="flex flex-col leading-none">
              <span className="font-heading text-[15px] font-bold tracking-tight">ZapPedidos</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                LAD Delivery API v1
              </span>
            </span>
          </Link>
          <nav className="ml-6 hidden items-center gap-1 md:flex">
            {items.map((item) => {
              const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  data-testid={item.testid}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors duration-150",
                    active
                      ? "bg-primary/12 text-primary"
                      : "text-muted-foreground hover:bg-secondary hover:text-foreground",
                  )}
                >
                  <item.icon className="size-4" />
                  {item.label}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-3">
            {user && (
              <span className="hidden text-right leading-tight sm:block" data-testid="current-user">
                <span className="block text-sm">{user.nome || user.email}</span>
                <span className="block font-mono text-[10px] uppercase tracking-[0.16em] text-primary">
                  {user.role === "admin" ? "Revendedor" : "Lojista"}
                </span>
              </span>
            )}
            <Button variant="ghost" size="sm" onClick={sair} data-testid="logout-button">
              <LogOut className="size-4" /> Sair
            </Button>
          </div>
        </div>
      </header>
      <nav className="flex gap-1 overflow-x-auto border-b border-border px-4 py-2 md:hidden">
        {items.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            data-testid={`${item.testid}-mobile`}
            className="whitespace-nowrap rounded-lg px-3 py-1.5 text-xs text-muted-foreground"
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <main className="mx-auto max-w-7xl px-5 py-8">{children}</main>
    </div>
  );
}
