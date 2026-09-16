import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { BrowserRouter } from "react-router-dom";
import {
  Activity, Bot, Building2, Check, ChevronRight, CircleUserRound, Download,
  LayoutDashboard, LogOut, MessageSquare, Package, Pencil, Plus, Power,
  RefreshCw, Server, Settings2, ShieldCheck, ShoppingCart, Store, Trash2,
  Users, X, Zap,
} from "lucide-react";
import "@/App.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const api = axios.create({ baseURL: API, withCredentials: true });
const money = (v) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v || 0);

function App() { return <BrowserRouter><Panel /></BrowserRouter>; }

function Panel() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState("overview");
  const [stores, setStores] = useState([]);
  const [plans, setPlans] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [notice, setNotice] = useState(null);
  const [login, setLogin] = useState({ email: "admin@zappedidos.com", senha: "Zap@2026" });

  const isStaff = user && ["admin", "reseller"].includes(user.role);
  const selectedStore = stores.find((s) => s.id === selectedId) || stores[0];

  const flash = useCallback((msg, tone = "ok") => {
    setNotice({ msg, tone });
    setTimeout(() => setNotice(null), 4500);
  }, []);

  const loadStores = useCallback(async () => {
    const r = await api.get("/dashboard");
    setStores(r.data.lojas);
    if (!selectedId && r.data.lojas.length) setSelectedId(r.data.lojas[0].id);
  }, [selectedId]);

  useEffect(() => {
    (async () => {
      try {
        const me = await api.get("/auth/me");
        setUser(me.data);
        const data = await api.get("/dashboard");
        setStores(data.data.lojas);
        setPlans((await api.get("/plans")).data);
        if (data.data.lojas.length) setSelectedId(data.data.lojas[0].id);
      } catch {
        setUser(false);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function signIn(e) {
    e.preventDefault();
    try {
      const r = await api.post("/auth/login", login);
      setUser(r.data);
      const data = await api.get("/dashboard");
      setStores(data.data.lojas);
      setPlans((await api.get("/plans")).data);
      if (data.data.lojas.length) setSelectedId(data.data.lojas[0].id);
      flash("Bem-vindo ao ZapPedidos");
    } catch (err) {
      flash(err.response?.data?.detail || "E-mail ou senha inválidos", "err");
    }
  }

  async function signOut() {
    await api.post("/auth/logout");
    setUser(false);
    setStores([]);
    setSelectedId(null);
    setPage("overview");
  }

  if (loading) return <div className="loading-screen">Carregando seu painel<span>●</span></div>;
  if (!user) return <LoginView login={login} setLogin={setLogin} signIn={signIn} notice={notice} />;

  const menu = [
    ["overview", LayoutDashboard, isStaff ? "Visão geral" : "Meu painel"],
    ...(isStaff ? [["stores", Building2, "Lojas e clientes"], ["plans", ShieldCheck, "Planos"]] : []),
    ["catalog", Package, "Catálogo"],
    ["connection", Server, "Conectar WhatsApp"],
    ["orders", ShoppingCart, "Pedidos"],
    ["chats", MessageSquare, "Conversas"],
    ["settings", Settings2, "Configurações"],
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Bot size={19} /></span>
          <div><strong>ZapPedidos</strong><small>Control center</small></div>
        </div>
        <div className="workspace-label">{isStaff ? "OPERAÇÃO" : "MINHA LOJA"}</div>
        <nav>
          {menu.map(([key, Icon, label]) => (
            <button
              key={key}
              className={page === key ? "nav-item active" : "nav-item"}
              onClick={() => setPage(key)}
              data-testid={`nav-${key}`}
            >
              <Icon size={17} />{label}
              {key === "connection" && selectedStore?.wa_status === "connected" && <i className="dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="account-mini">
            <CircleUserRound size={25} />
            <div>
              <strong>{user.nome}</strong>
              <small>{user.role === "admin" ? "Administrador geral" : user.role === "reseller" ? "Revendedor" : "Cliente"}</small>
            </div>
          </div>
          <button className="logout" onClick={signOut} data-testid="logout-button"><LogOut size={16} />Sair</button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow">{isStaff ? "PAINEL ADMINISTRATIVO" : "ÁREA DO CLIENTE"}</span>
            <h1>{page === "overview" ? `Bom dia, ${(user.nome?.split(" ")[0]) || "equipe"}` : pageTitle(page)}</h1>
          </div>
          <div className="top-actions">
            {stores.length > 0 && (
              <select value={selectedStore?.id || ""} onChange={(e) => setSelectedId(e.target.value)} data-testid="store-selector">
                {stores.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            )}
            <span className="live"><i /> Sistema online</span>
          </div>
        </header>

        {notice && (
          <div className={`notice ${notice.tone}`} data-testid="notice">
            {notice.tone === "err" ? <X size={16} /> : <Check size={16} />}
            {notice.msg}
            <button onClick={() => setNotice(null)}><X size={15} /></button>
          </div>
        )}

        {page === "overview" && <Overview stores={stores} user={user} setPage={setPage} setSelectedId={setSelectedId} />}
        {page === "stores" && <StoresPage stores={stores} loadStores={loadStores} setSelectedId={setSelectedId} setPage={setPage} flash={flash} />}
        {page === "plans" && <PlansPage plans={plans} stores={stores} />}
        {page === "catalog" && <CatalogPage store={selectedStore} flash={flash} />}
        {page === "connection" && <ConnectionPage store={selectedStore} loadStores={loadStores} flash={flash} />}
        {page === "orders" && <OrdersPage store={selectedStore} flash={flash} />}
        {page === "chats" && <ChatsPage store={selectedStore} />}
        {page === "settings" && <SettingsPage user={user} store={selectedStore} loadStores={loadStores} flash={flash} />}
      </main>
    </div>
  );
}

// ============================================================ Login
function LoginView({ login, setLogin, signIn, notice }) {
  return (
    <div className="login-page">
      <div className="login-art">
        <div className="brand">
          <span className="brand-mark"><Bot size={19} /></span>
          <div><strong>ZapPedidos</strong><small>Reseller workspace</small></div>
        </div>
        <div className="art-copy">
          <span className="eyebrow">AUTOMAÇÃO PARA DELIVERY</span>
          <h1>Seu WhatsApp,<br /><em>sob controle.</em></h1>
          <p>Uma operação inteira para conectar clientes, acompanhar lojas e fazer cada pedido avançar — WAHA ou Evolution API à sua escolha.</p>
          <div className="art-proof">
            <span><Activity size={16} /> Status em tempo real</span>
            <span><ShieldCheck size={16} /> Multi-tenant seguro</span>
            <span><Zap size={16} /> LAD Delivery integrada</span>
          </div>
        </div>
      </div>
      <form className="login-form" onSubmit={signIn}>
        <div className="form-kicker">ACESSO RESTRITO</div>
        <h2>Entrar no painel</h2>
        <p className="muted">Use suas credenciais para continuar.</p>
        <label>E-mail<input type="email" value={login.email} onChange={(e) => setLogin({ ...login, email: e.target.value })} data-testid="login-email-input" /></label>
        <label>Senha<input type="password" value={login.senha} onChange={(e) => setLogin({ ...login, senha: e.target.value })} data-testid="login-password-input" /></label>
        {notice && notice.tone === "err" && <div className="error">{notice.msg}</div>}
        <button className="primary wide" type="submit" data-testid="login-submit-button">Entrar no workspace <ChevronRight size={17} /></button>
        <small className="login-hint">Administrador inicial: admin@zappedidos.com</small>
      </form>
    </div>
  );
}

// ============================================================ Overview
function Overview({ stores, user, setPage, setSelectedId }) {
  const connected = stores.filter((s) => s.wa_status === "connected").length;
  return (
    <>
      <section className="hero">
        <div>
          <span className="eyebrow">{new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" })}</span>
          <h2>Uma visão clara da<br /><em>sua operação.</em></h2>
          <p>Gerencie conexões, catálogos e pedidos dos seus clientes em um único painel.</p>
        </div>
        <div className="hero-signal">
          <div className="signal-ring"><Bot size={27} /></div>
          <strong>WA CORE</strong>
          <span>WAHA · Evolution</span>
        </div>
      </section>
      <div className="metrics">
        <Metric label="Lojas ativas" value={stores.length} detail="clientes na base" icon={Building2} />
        <Metric label="WhatsApp conectado" value={connected} detail={`de ${stores.length} instâncias`} icon={Activity} accent="green" />
        <Metric label="Planos em uso" value={new Set(stores.map((s) => s.plano)).size} detail="configurações ativas" icon={ShieldCheck} accent="amber" />
        <Metric label="Bot em operação" value={stores.filter((s) => s.bot_ativo).length} detail="atendentes ligados" icon={Bot} accent="blue" />
      </div>
      <div className="section-head">
        <div><span className="eyebrow">CENTRAL DE OPERAÇÃO</span><h3>{user.role === "client" ? "Sua loja" : "Lojas recentes"}</h3></div>
        {user.role !== "client" && <button className="ghost" onClick={() => setPage("stores")} data-testid="manage-stores-button">Ver todas <ChevronRight size={15} /></button>}
      </div>
      <div className="store-grid">
        {stores.slice(0, 4).map((s) => (
          <StoreCard key={s.id} store={s} open={() => { setSelectedId(s.id); setPage("connection"); }} />
        ))}
        {!stores.length && <div className="empty">Nenhuma loja cadastrada ainda. Abra "Lojas e clientes" para começar.</div>}
      </div>
    </>
  );
}

function Metric({ label, value, detail, icon: Icon, accent = "" }) {
  return (
    <div className="metric" data-testid={`metric-${label.toLowerCase().replaceAll(" ", "-")}`}>
      <div className={`metric-icon ${accent}`}><Icon size={18} /></div>
      <div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
    </div>
  );
}

function StoreCard({ store, open }) {
  const status = store.wa_status || "not_configured";
  return (
    <button className="store-card" onClick={open} data-testid={`store-card-${store.id}`}>
      <div className="store-card-top">
        <span className="store-avatar"><Store size={18} /></span>
        <span className={status === "connected" ? "status connected" : "status pending"}>
          <i />{status === "connected" ? "Conectado" : status === "not_configured" ? "Configurar" : "Aguardando"}
        </span>
      </div>
      <strong>{store.nome}</strong>
      <span className="store-email">{store.cliente_email}</span>
      <div className="store-card-bottom"><span>{store.plano}</span><ChevronRight size={15} /></div>
    </button>
  );
}

// ============================================================ Stores
function StoresPage({ stores, loadStores, setSelectedId, setPage, flash }) {
  const [form, setForm] = useState({ nome: "", cliente_email: "", cliente_senha: "", plano: "Essencial", lad_token: "" });

  async function submit(e) {
    e.preventDefault();
    try {
      await api.post("/stores", form);
      setForm({ nome: "", cliente_email: "", cliente_senha: "", plano: "Essencial", lad_token: "" });
      await loadStores();
      flash("Loja criada e acesso do cliente enviado");
    } catch (err) {
      flash(err.response?.data?.detail || "Revise os dados da loja", "err");
    }
  }

  async function remove(id) {
    if (!window.confirm("Excluir esta loja e todos os dados?")) return;
    await api.delete(`/stores/${id}`);
    await loadStores();
    flash("Loja excluída");
  }

  return (
    <>
      <div className="section-head">
        <div><span className="eyebrow">BASE DE CLIENTES</span><h2>Lojas e clientes</h2></div>
        <span className="count-pill">{stores.length} lojas</span>
      </div>
      <div className="content-grid">
        <div className="panel">
          <div className="panel-head"><div><h3>Adicionar uma loja</h3><p>Crie a loja e o acesso do cliente em uma única etapa.</p></div><Plus size={19} /></div>
          <form className="stack-form" onSubmit={submit}>
            <label>Nome da loja<input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: Ponto do Açaí" data-testid="store-name-input" /></label>
            <label>E-mail do cliente<input required type="email" value={form.cliente_email} onChange={(e) => setForm({ ...form, cliente_email: e.target.value })} placeholder="cliente@empresa.com" data-testid="client-email-input" /></label>
            <div className="two-cols">
              <label>Senha inicial<input type="password" required value={form.cliente_senha} onChange={(e) => setForm({ ...form, cliente_senha: e.target.value })} data-testid="client-password-input" /></label>
              <label>Plano<select value={form.plano} onChange={(e) => setForm({ ...form, plano: e.target.value })} data-testid="plan-select">
                <option>Essencial</option><option>Crescimento</option><option>Escala</option>
              </select></label>
            </div>
            <label>Token LAD Delivery <span className="optional">opcional</span><input value={form.lad_token} onChange={(e) => setForm({ ...form, lad_token: e.target.value })} placeholder="Bearer token" data-testid="lad-token-input" /></label>
            <button className="primary" type="submit" data-testid="create-store-button">Criar loja <Plus size={16} /></button>
          </form>
        </div>
        <div className="panel">
          <div className="panel-head"><div><h3>Clientes cadastrados</h3><p>Selecione uma loja para configurar a conexão.</p></div><Users size={19} /></div>
          <div className="client-list">
            {stores.map((s) => (
              <div className="client-row" key={s.id} data-testid={`client-row-${s.id}`}>
                <button className="client-btn" onClick={() => { setSelectedId(s.id); setPage("connection"); }}>
                  <span className="store-avatar small"><Store size={15} /></span>
                  <span><strong>{s.nome}</strong><small>{s.cliente_email}</small></span>
                  <span className="row-plan">{s.plano}</span>
                </button>
                <button className="icon-btn danger" onClick={() => remove(s.id)} data-testid={`delete-store-${s.id}`}><Trash2 size={14} /></button>
              </div>
            ))}
            {!stores.length && <div className="empty compact">Cadastre a primeira loja no formulário ao lado.</div>}
          </div>
        </div>
      </div>
    </>
  );
}

// ============================================================ Plans
function PlansPage({ plans, stores }) {
  return (
    <>
      <div className="section-head"><div><span className="eyebrow">MODELO COMERCIAL</span><h2>Planos de revenda</h2></div></div>
      <div className="plans-grid">
        {plans.map((plan) => (
          <div className="plan-card" key={plan.id}>
            <span className={`plan-dot ${plan.cor}`} />
            <h3>{plan.nome}</h3>
            <strong>{money(plan.preco)}<small>/mês</small></strong>
            <p>Até {plan.limite_lojas > 900 ? "lojas ilimitadas" : `${plan.limite_lojas} lojas`} por cliente</p>
            <div className="plan-used"><span>Em uso</span><b>{stores.filter((s) => s.plano === plan.nome).length}</b></div>
          </div>
        ))}
      </div>
    </>
  );
}

// ============================================================ Catalog (CRUD completo)
function CatalogPage({ store, flash }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ nome: "", descricao: "", preco: "", categoria: "Geral" });
  const [editing, setEditing] = useState(null);

  const reload = useCallback(async () => {
    if (!store) return;
    const r = await api.get(`/stores/${store.id}/products`);
    setItems(r.data);
  }, [store]);

  useEffect(() => { reload(); }, [reload]);

  if (!store) return <EmptySelect />;

  async function submit(e) {
    e.preventDefault();
    try {
      if (editing) {
        await api.patch(`/stores/${store.id}/products/${editing}`, { ...form, preco: Number(form.preco) });
        flash("Produto atualizado");
      } else {
        await api.post(`/stores/${store.id}/products`, { ...form, preco: Number(form.preco) });
        flash("Produto adicionado");
      }
      setForm({ nome: "", descricao: "", preco: "", categoria: "Geral" });
      setEditing(null);
      reload();
    } catch (err) {
      flash(err.response?.data?.detail || "Verifique os dados", "err");
    }
  }

  async function remove(id) {
    if (!window.confirm("Excluir este produto?")) return;
    await api.delete(`/stores/${store.id}/products/${id}`);
    flash("Produto excluído");
    reload();
  }

  async function toggle(item) {
    await api.patch(`/stores/${store.id}/products/${item.id}`, { ativo: !item.ativo });
    reload();
  }

  function edit(item) {
    setEditing(item.id);
    setForm({ nome: item.nome, descricao: item.descricao || "", preco: item.preco, categoria: item.categoria });
  }

  async function importCatalog() {
    try {
      const r = await api.post(`/stores/${store.id}/lad/cardapio/importar`);
      flash(`Importados ${r.data.importados}, atualizados ${r.data.atualizados}`);
      reload();
    } catch (err) {
      flash(err.response?.data?.detail || "Configure o token LAD nas configurações da loja", "err");
    }
  }

  return (
    <>
      <div className="section-head">
        <div><span className="eyebrow">CARDÁPIO DIGITAL · {store.nome}</span><h2>Catálogo de produtos</h2></div>
        <div className="head-actions">
          <button className="ghost" onClick={importCatalog} data-testid="import-lad-button"><Download size={15} /> Importar da LAD</button>
          <span className="count-pill">{items.length} itens</span>
        </div>
      </div>
      <div className="content-grid">
        <div className="panel">
          <div className="panel-head">
            <div><h3>{editing ? "Editar produto" : "Novo produto"}</h3><p>O bot usa estes itens para montar pedidos.</p></div>
            <Package size={19} />
          </div>
          <form className="stack-form" onSubmit={submit}>
            <label>Nome<input required value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} placeholder="Ex.: X-Bacon" data-testid="product-name-input" /></label>
            <label>Descrição<input value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} placeholder="Ingredientes e detalhes" data-testid="product-description-input" /></label>
            <div className="two-cols">
              <label>Preço<input required type="number" step="0.01" value={form.preco} onChange={(e) => setForm({ ...form, preco: e.target.value })} placeholder="0,00" data-testid="product-price-input" /></label>
              <label>Categoria<input value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })} data-testid="product-category-input" /></label>
            </div>
            <div className="row-actions">
              <button className="primary" type="submit" data-testid="save-product-button">{editing ? "Salvar alterações" : "Adicionar produto"} <Plus size={16} /></button>
              {editing && <button type="button" className="ghost" onClick={() => { setEditing(null); setForm({ nome: "", descricao: "", preco: "", categoria: "Geral" }); }}>Cancelar</button>}
            </div>
          </form>
        </div>
        <div className="panel">
          <div className="panel-head"><div><h3>Itens do cardápio</h3><p>Ative, edite ou remova produtos.</p></div></div>
          <div className="product-list">
            {items.map((item) => (
              <div className={`product-row ${item.ativo ? "" : "inactive"}`} key={item.id}>
                <span className="product-icon"><Package size={16} /></span>
                <span><strong>{item.nome}</strong><small>{item.categoria} · {item.descricao || "Sem descrição"}</small></span>
                <b>{money(item.preco)}</b>
                <div className="row-icons">
                  <button className="icon-btn" onClick={() => toggle(item)} data-testid={`toggle-product-${item.id}`} title={item.ativo ? "Desativar" : "Ativar"}>
                    <Power size={14} className={item.ativo ? "on" : "off"} />
                  </button>
                  <button className="icon-btn" onClick={() => edit(item)} data-testid={`edit-product-${item.id}`}><Pencil size={14} /></button>
                  <button className="icon-btn danger" onClick={() => remove(item.id)} data-testid={`delete-product-${item.id}`}><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
            {!items.length && <div className="empty compact">Nenhum produto ainda. Adicione manualmente ou importe da LAD.</div>}
          </div>
        </div>
      </div>
    </>
  );
}

// ============================================================ Connection (QR + provider)
function ConnectionPage({ store, loadStores, flash }) {
  const [setupForm, setSetupForm] = useState({ provider: "waha", base_url: "", api_token: "", session_name: "" });
  const [state, setState] = useState(null);
  const [qr, setQr] = useState({ qr: null, message: "" });
  const [busy, setBusy] = useState(false);
  const pollRef = useRef();

  const loadState = useCallback(async () => {
    if (!store) return;
    try {
      const r = await api.get(`/stores/${store.id}/whatsapp`);
      setState(r.data);
      if (r.data.configured && r.data.status !== "connected") {
        const q = await api.get(`/stores/${store.id}/whatsapp/qr`);
        setQr(q.data);
        if (q.data.status === "connected") await loadStores();
      } else if (r.data.status === "connected") {
        setQr({ qr: null, message: "WhatsApp conectado" });
      }
    } catch {
      // Provider externo indisponível — o status já é mostrado no card, sem toast
      setState((prev) => prev || { status: "offline", configured: !!store.wa_url, session: store.wa_session });
    }
  }, [store, loadStores]);

  useEffect(() => {
    loadState();
    return () => clearInterval(pollRef.current);
  }, [loadState]);

  // Auto polling a cada 5s enquanto está pendente
  useEffect(() => {
    clearInterval(pollRef.current);
    if (!state?.configured) return;
    if (state.status === "connected") return;
    pollRef.current = setInterval(loadState, 5000);
    return () => clearInterval(pollRef.current);
  }, [state, loadState]);

  if (!store) return <EmptySelect />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const r = await api.post(`/stores/${store.id}/whatsapp/setup`, setupForm);
      flash(r.data.message || "Sessão iniciada");
      await loadState();
      await loadStores();
    } catch (err) {
      flash(err.response?.data?.detail || "Verifique os dados do provider", "err");
    } finally {
      setBusy(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Desconectar o WhatsApp desta loja?")) return;
    await api.post(`/stores/${store.id}/whatsapp/disconnect`);
    flash("WhatsApp desconectado");
    await loadState();
    await loadStores();
  }

  const status = state?.status || store.wa_status || "not_configured";
  const statusLabel = {
    connected: "Conectado",
    qr_pending: "Escaneie o QR code",
    pending: "Iniciando",
    offline: "Desconectado",
    not_configured: "Não configurado",
    not_started: "Sessão não iniciada",
    error: "Erro na conexão",
  }[status] || status;

  return (
    <>
      <div className="section-head">
        <div><span className="eyebrow">CONEXÃO POR CLIENTE · {store.nome}</span><h2>Conectar WhatsApp</h2></div>
        <span className={`status large ${status === "connected" ? "connected" : "pending"}`} data-testid="wa-status">
          <i />{statusLabel}
        </span>
      </div>
      <div className="connection-layout">
        <div className="connection-main">
          <div className="connection-visual">
            <div className="qr-placeholder" data-testid="qr-container">
              {qr.qr ? (
                <img src={qr.qr} alt="QR Code WhatsApp" data-testid="qr-image" />
              ) : status === "connected" ? (
                <>
                  <Check size={40} />
                  <span>WhatsApp ativo</span>
                  <small>Sessão {state?.session}</small>
                </>
              ) : (
                <>
                  <Server size={34} />
                  <span>{state?.configured ? "Aguardando QR" : "Configure o provider"}</span>
                  <small>{qr.message || "Preencha os dados da instância ao lado"}</small>
                </>
              )}
            </div>
            <div>
              <span className="eyebrow">INSTÂNCIA EXCLUSIVA</span>
              <h3>{state?.session || `zp_${store.id.slice(0, 10)}`}</h3>
              <p>Cada cliente possui a própria sessão isolada. WAHA ou Evolution — nunca as duas ao mesmo tempo. Escaneie no WhatsApp &gt; Dispositivos conectados.</p>
              <div className="row-actions">
                <button className="ghost" onClick={loadState} data-testid="refresh-qr-button"><RefreshCw size={15} /> Atualizar</button>
                {state?.configured && status !== "not_configured" && (
                  <button className="danger-btn" onClick={disconnect} data-testid="disconnect-button"><Power size={15} /> Desconectar</button>
                )}
              </div>
            </div>
          </div>
        </div>
        <div className="panel connection-form">
          <div className="panel-head"><div><h3>Configurar instância</h3><p>Informe URL e token do seu WAHA ou Evolution API.</p></div><Server size={19} /></div>
          <form className="stack-form" onSubmit={submit}>
            <label>Provider
              <select value={setupForm.provider} onChange={(e) => setSetupForm({ ...setupForm, provider: e.target.value })} data-testid="provider-select">
                <option value="waha">WAHA (devlikeapro)</option>
                <option value="evolution">Evolution API</option>
              </select>
            </label>
            <label>URL da instância<input required value={setupForm.base_url} onChange={(e) => setSetupForm({ ...setupForm, base_url: e.target.value })} placeholder="https://waha.seudominio.com" data-testid="wa-url-input" /></label>
            <label>Token da API<input required type="password" value={setupForm.api_token} onChange={(e) => setSetupForm({ ...setupForm, api_token: e.target.value })} placeholder="API key ou apikey global" data-testid="wa-token-input" /></label>
            <label>Nome da sessão <span className="optional">opcional</span><input value={setupForm.session_name} onChange={(e) => setSetupForm({ ...setupForm, session_name: e.target.value })} placeholder={`zp_${store.id.slice(0, 8)}`} data-testid="wa-session-input" /></label>
            <button className="primary" type="submit" disabled={busy} data-testid="save-wa-button">
              {busy ? "Iniciando..." : "Salvar e iniciar"} <ChevronRight size={16} />
            </button>
          </form>
        </div>
      </div>
    </>
  );
}

// ============================================================ Orders
function OrdersPage({ store, flash }) {
  const [orders, setOrders] = useState([]);
  const reload = useCallback(async () => {
    if (!store) return;
    const r = await api.get(`/stores/${store.id}/orders`);
    setOrders(r.data);
  }, [store]);

  useEffect(() => { reload(); }, [reload]);

  if (!store) return <EmptySelect />;

  async function refresh(id) {
    try {
      await api.post(`/stores/${store.id}/orders/${id}/refresh`);
      reload();
    } catch (err) {
      flash(err.response?.data?.detail || "Falha ao consultar LAD", "err");
    }
  }

  return (
    <>
      <div className="section-head">
        <div><span className="eyebrow">FLUXO OPERACIONAL · {store.nome}</span><h2>Pedidos</h2></div>
        <span className="count-pill">{orders.length} pedidos</span>
      </div>
      <div className="panel">
        <div className="panel-head"><div><h3>Últimos pedidos</h3><p>Criados a partir do bot ou da API LAD.</p></div><ShoppingCart size={19} /></div>
        <div className="product-list">
          {orders.map((o) => (
            <div className="product-row" key={o.id}>
              <span className="product-icon"><ShoppingCart size={16} /></span>
              <span>
                <strong>#{(o.uuid_lad || o.id).slice(0, 8).toUpperCase()}</strong>
                <small>{o.tipo || "DELIVERY"} · {new Date(o.created_at).toLocaleString("pt-BR")}</small>
              </span>
              <span className="row-plan">{o.status}</span>
              <b>{money(o.valor_total)}</b>
              <button className="icon-btn" onClick={() => refresh(o.id)} title="Atualizar status" data-testid={`refresh-order-${o.id}`}><RefreshCw size={14} /></button>
            </div>
          ))}
          {!orders.length && <div className="empty compact">Sem pedidos ainda. Quando o bot processar um pedido pela LAD, ele aparece aqui.</div>}
        </div>
      </div>
    </>
  );
}

// ============================================================ Chats
function ChatsPage({ store }) {
  const [chats, setChats] = useState([]);
  useEffect(() => {
    if (!store) return;
    const load = async () => {
      const r = await api.get(`/stores/${store.id}/chats`);
      setChats(r.data);
    };
    load();
    const interval = setInterval(load, 8000);
    return () => clearInterval(interval);
  }, [store]);

  if (!store) return <EmptySelect />;
  return (
    <>
      <div className="section-head">
        <div><span className="eyebrow">CENTRAL DE CONVERSAS · {store.nome}</span><h2>Conversas WhatsApp</h2></div>
        <span className="count-pill">{chats.length} contatos</span>
      </div>
      <div className="panel">
        <div className="panel-head"><div><h3>Últimas mensagens</h3><p>Recebidas via webhook do WAHA/Evolution.</p></div><MessageSquare size={19} /></div>
        <div className="product-list">
          {chats.map((c) => (
            <div className="product-row" key={c.remote}>
              <span className="product-icon"><MessageSquare size={16} /></span>
              <span>
                <strong>{c.remote}</strong>
                <small>{c.ultima?.slice(0, 90) || "(sem texto)"}</small>
              </span>
              <span className="row-plan">{new Date(c.quando).toLocaleTimeString("pt-BR")}</span>
            </div>
          ))}
          {!chats.length && <div className="empty compact">Sem conversas ainda. Configure o webhook: <code>{`${window.location.origin.replace(":3000", "")}/api/webhooks/whatsapp/${store.id}`}</code></div>}
        </div>
      </div>
    </>
  );
}

// ============================================================ Settings (com LAD token, MP token e bot ativo)
function SettingsPage({ user, store, loadStores, flash }) {
  const [ladToken, setLadToken] = useState("");
  const [botAtivo, setBotAtivo] = useState(!!store?.bot_ativo);
  const [mpToken, setMpToken] = useState("");
  const [mpAmbiente, setMpAmbiente] = useState("producao");
  const [mpState, setMpState] = useState({ configured: false, ambiente: "producao" });
  const [pixTest, setPixTest] = useState(null);
  const [storeDetail, setStoreDetail] = useState(null);

  const loadDetail = useCallback(async () => {
    if (!store) return;
    const r = await api.get(`/stores/${store.id}`);
    setStoreDetail(r.data);
    const m = await api.get(`/stores/${store.id}/mercadopago`);
    setMpState(m.data);
    setMpAmbiente(m.data.ambiente);
  }, [store]);

  useEffect(() => {
    setBotAtivo(!!store?.bot_ativo);
    setLadToken("");
    setMpToken("");
    setPixTest(null);
    loadDetail();
  }, [store?.id, loadDetail]);

  async function saveToken() {
    if (!store) return;
    try {
      await api.patch(`/stores/${store.id}`, { lad_token: ladToken });
      flash("Token LAD salvo");
      setLadToken("");
      loadStores();
      loadDetail();
    } catch (err) {
      flash(err.response?.data?.detail || "Falha ao salvar", "err");
    }
  }

  async function toggleBot() {
    if (!store) return;
    const next = !botAtivo;
    setBotAtivo(next);
    await api.patch(`/stores/${store.id}`, { bot_ativo: next });
    flash(next ? "Bot ativado" : "Bot desativado");
    loadStores();
  }

  async function saveMpToken() {
    if (!store || !mpToken) return;
    try {
      await api.post(`/stores/${store.id}/mercadopago/setup`, { access_token: mpToken, ambiente: mpAmbiente });
      flash("Access Token Mercado Pago salvo");
      setMpToken("");
      loadDetail();
    } catch (err) {
      flash(err.response?.data?.detail || "Falha ao salvar token", "err");
    }
  }

  async function removeMp() {
    if (!store) return;
    if (!window.confirm("Remover o token do Mercado Pago desta loja?")) return;
    await api.delete(`/stores/${store.id}/mercadopago`);
    flash("Token Mercado Pago removido");
    loadDetail();
  }

  async function testPix() {
    if (!store) return;
    try {
      const r = await api.post(`/stores/${store.id}/mercadopago/pix`, {
        valor: 1.00,
        descricao: "Teste ZapPedidos",
        email_pagador: user.email,
      });
      setPixTest(r.data);
      flash("PIX de teste criado (R$ 1,00)");
    } catch (err) {
      flash(err.response?.data?.detail || "Falha ao criar PIX", "err");
    }
  }

  return (
    <div className="settings-wrap">
      <span className="eyebrow">PREFERÊNCIAS</span>
      <h2>Configurações</h2>
      <div className="panel settings-card">
        <div className="account-row">
          <span className="store-avatar"><CircleUserRound size={19} /></span>
          <div><strong>{user.nome}</strong><small>{user.email}</small></div>
          <span className="row-plan">{user.role}</span>
        </div>
        {store && (
          <>
            <div className="setting-line">
              <span><strong>Bot ativo</strong><small>{store.nome} responde automaticamente pelo WhatsApp</small></span>
              <button className={`toggle ${botAtivo ? "on" : ""}`} onClick={toggleBot} data-testid="toggle-bot"><i /></button>
            </div>
            <div className="setting-line stacked">
              <div><strong>Token LAD Delivery</strong><small>Usado para sincronizar cardápio e criar pedidos</small></div>
              <div className="inline-form">
                <input type="password" value={ladToken} onChange={(e) => setLadToken(e.target.value)} placeholder={storeDetail?.has_lad_token ? "Token configurado · digite para substituir" : "Cole o Bearer token"} data-testid="settings-lad-token" />
                <button className="primary" onClick={saveToken} disabled={!ladToken} data-testid="save-lad-token">Salvar token</button>
              </div>
            </div>
            <div className="setting-line stacked mp-block">
              <div className="mp-header">
                <div>
                  <strong>Mercado Pago</strong>
                  <small>Cadastre seu Access Token para receber pagamentos via PIX e Checkout Pro</small>
                </div>
                <span className={`mp-badge ${mpState.configured ? "on" : ""}`} data-testid="mp-badge">
                  <i />{mpState.configured ? `Configurado · ${mpState.ambiente}` : "Não configurado"}
                </span>
              </div>
              <div className="two-cols">
                <label>Access Token
                  <input type="password" value={mpToken} onChange={(e) => setMpToken(e.target.value)} placeholder={mpState.configured ? "Token configurado · digite para substituir" : "APP_USR-... ou TEST-..."} data-testid="mp-token-input" />
                </label>
                <label>Ambiente
                  <select value={mpAmbiente} onChange={(e) => setMpAmbiente(e.target.value)} data-testid="mp-env-select">
                    <option value="producao">Produção</option>
                    <option value="teste">Teste (sandbox)</option>
                  </select>
                </label>
              </div>
              <div className="row-actions">
                <button className="primary" onClick={saveMpToken} disabled={!mpToken} data-testid="save-mp-token">Salvar token</button>
                {mpState.configured && (
                  <>
                    <button className="ghost" onClick={testPix} data-testid="test-pix-button"><Zap size={14} /> Testar PIX de R$ 1,00</button>
                    <button className="danger-btn" onClick={removeMp} data-testid="remove-mp-button"><Trash2 size={14} /> Remover</button>
                  </>
                )}
              </div>
              <small className="mp-hint">
                Como obter? Mercado Pago → Suas integrações → Aplicação → Credenciais de {mpAmbiente === "producao" ? "produção" : "teste"} → Access Token
              </small>
              {pixTest && (
                <div className="pix-result" data-testid="pix-test-result">
                  <strong>PIX de teste gerado</strong>
                  {pixTest.qr_code_base64 && (
                    <img alt="QR PIX" src={`data:image/png;base64,${pixTest.qr_code_base64}`} className="pix-qr" />
                  )}
                  <label>Copia e cola PIX
                    <input readOnly value={pixTest.copia_e_cola || ""} onFocus={(e) => e.target.select()} />
                  </label>
                  <small>Status: <b>{pixTest.status}</b> · Referência: <code>{pixTest.referencia}</code></small>
                </div>
              )}
            </div>
            <div className="setting-line">
              <span><strong>Webhook WhatsApp</strong><small>Configure no seu WAHA/Evolution para receber conversas</small></span>
              <code className="webhook-url">{process.env.REACT_APP_BACKEND_URL}/api/webhooks/whatsapp/{store.id}</code>
            </div>
            <div className="setting-line">
              <span><strong>Webhook Mercado Pago</strong><small>Configure no painel MP → Webhooks para receber notificações</small></span>
              <code className="webhook-url">{process.env.REACT_APP_BACKEND_URL}/api/webhooks/mercadopago/{store.id}</code>
            </div>
          </>
        )}
        <div className="setting-line">
          <span><strong>Ambiente da operação</strong><small>Todos os dados ficam isolados por cliente</small></span>
          <span className="secure"><ShieldCheck size={15} /> Seguro</span>
        </div>
      </div>
    </div>
  );
}

function EmptySelect() {
  return (
    <div className="empty-select">
      <Store size={30} />
      <h2>Selecione uma loja</h2>
      <p>Escolha uma loja no seletor acima para continuar.</p>
    </div>
  );
}

function pageTitle(page) {
  return {
    stores: "Lojas e clientes",
    plans: "Planos de revenda",
    catalog: "Catálogo",
    connection: "Conectar WhatsApp",
    orders: "Pedidos",
    chats: "Conversas",
    settings: "Configurações",
  }[page];
}

export default App;
