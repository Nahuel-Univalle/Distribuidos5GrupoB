import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import {
  AlertTriangle,
  Bell,
  Droplet,
  Gauge,
  LayoutDashboard,
  LogOut,
  Map,
  Monitor,
  Receipt,
  Search,
  Sparkles,
} from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/mapa", label: "Mapa territorial", icon: Map },
  { to: "/consultas", label: "Consultas", icon: Gauge },
  { to: "/facturacion", label: "Facturación", icon: Receipt },
  { to: "/anomalias", label: "Alertas", icon: AlertTriangle },
];

export default function Layout() {
  const { rol, nombre, logout } = useAuthStore();
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);

  async function buscar() {
    if (!q || q.length < 2) return;
    setBusy(true);
    try {
      const r = await api.get("/buscar", { params: { q } });
      setResults(r.data.results || []);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full bg-slate-100 text-slate-950 lg:grid lg:grid-cols-[286px_1fr]">
      <aside className="hidden border-r border-blue-900/30 bg-gradient-to-b from-sky-950 via-blue-950 to-slate-950 p-4 text-white lg:flex lg:flex-col">
        <div className="mb-7 rounded-[28px] border border-white/10 bg-white/10 p-4 shadow-2xl backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl bg-cyan-400/15 p-3 ring-1 ring-cyan-300/20">
              <Droplet size={28} className="text-cyan-200" />
            </div>
            <div>
              <div className="text-xl font-black tracking-tight">SEMAPA</div>
              <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-100">Agua Inteligente</div>
            </div>
          </div>
          <div className="mt-4 rounded-2xl bg-white/10 p-3 text-xs leading-5 text-blue-100">
            Plataforma distribuida con Cassandra, IoT LoRaWAN, geodatos, facturación y mensajería.
          </div>
        </div>

        <nav className="flex flex-col gap-2 text-sm">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `group flex items-center gap-3 rounded-2xl px-4 py-3 font-bold transition ${
                  isActive
                    ? "bg-white text-blue-950 shadow-xl shadow-blue-950/20"
                    : "text-blue-100 hover:bg-white/10 hover:text-white"
                }`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
          <a
            href="/kiosk"
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-3 rounded-2xl px-4 py-3 font-bold text-cyan-100 transition hover:bg-white/10 hover:text-white"
          >
            <Monitor size={18} /> Autoservicio ↗
          </a>
        </nav>

        <div className="mt-auto space-y-4 pt-6">
          <div className="rounded-[24px] border border-white/10 bg-white/10 p-4 backdrop-blur">
            <div className="flex items-center gap-2 text-xs font-black uppercase tracking-[0.16em] text-cyan-100">
              <Sparkles size={14} /> Sesión
            </div>
            <div className="mt-3 font-black">{nombre || "Usuario"}</div>
            <div className="text-sm text-blue-100">{rol || "ROL"}</div>
            <button
              onClick={() => { logout(); navigate("/login"); }}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-white/10 px-3 py-2 text-sm font-black text-white hover:bg-white/15"
            >
              <LogOut size={16} /> Salir
            </button>
          </div>
        </div>
      </aside>

      <main className="min-w-0 overflow-auto">
        <header className="sticky top-0 z-30 border-b border-blue-100 bg-white/90 px-4 py-3 shadow-sm backdrop-blur lg:px-7">
          <div className="flex items-center gap-3">
            <div className="flex min-w-0 flex-1 items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2.5 focus-within:border-blue-300 focus-within:bg-white">
              <Search size={18} className="text-slate-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && buscar()}
                placeholder="Buscar por contrato, MAC, serie o documento..."
                className="w-full bg-transparent text-sm outline-none"
              />
              <button onClick={buscar} className="rounded-xl bg-blue-700 px-3 py-1.5 text-xs font-black text-white hover:bg-blue-800">
                {busy ? "Buscando..." : "Buscar"}
              </button>
            </div>
            <div className="hidden items-center gap-2 rounded-2xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs font-black text-blue-800 md:flex">
              <Bell size={14} /> Demo local
            </div>
          </div>
          {results.length > 0 && (
            <div className="absolute left-4 right-4 top-[68px] z-40 rounded-[22px] border border-blue-100 bg-white p-2 shadow-2xl lg:left-7 lg:right-auto lg:w-[720px]">
              {results.map((r, i) => (
                <div key={i} className="rounded-2xl p-3 text-xs hover:bg-blue-50">
                  <div className="font-black text-slate-900">{r.tipo}</div>
                  <div className="mt-1 font-mono text-slate-500">{JSON.stringify(r.payload).slice(0, 180)}…</div>
                </div>
              ))}
              <button className="w-full rounded-xl p-2 text-xs font-black text-blue-700 hover:bg-blue-50" onClick={() => setResults([])}>cerrar resultados</button>
            </div>
          )}
        </header>
        <div className="p-4 lg:p-7">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
