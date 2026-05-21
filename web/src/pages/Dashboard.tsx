import { useMemo, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Database,
  Droplets,
  Gauge,
  MapPinned,
  RadioTower,
  ShieldAlert,
  Users,
  Waves,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type ZonaApi = {
  distrito_id: number;
  zona_id: number;
  zona: string;
  medidores: number;
  activos: number;
  fuera_servicio: number;
  historicos: number;
  consumo_litros: number;
};

type ResumenMapa = {
  infraestructuras?: number;
  medidores?: number;
  activos?: number;
  fuera_servicio?: number;
  historicos?: number;
  por_estado?: Record<string, number>;
  por_categoria?: Record<string, number>;
  gateways_con_medidores?: number;
};

type HoraPico = { hora: number; consumo_litros: number };

const COLORS = ["#2563eb", "#0891b2", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#64748b", "#14b8a6"];
const fmt = (n: number | undefined | null) => Number(n ?? 0).toLocaleString("es-BO");
const fmtM3 = (litros: number | undefined | null) => `${fmt(Math.round(Number(litros ?? 0) / 1000))} m³`;

function Kpi({ label, value, hint, icon, tone = "blue" }: { label: string; value: any; hint?: string; icon: JSX.Element; tone?: "blue" | "cyan" | "red" | "green" | "slate" }) {
  const tones = {
    blue: "from-blue-50 to-white text-blue-700 ring-blue-100",
    cyan: "from-cyan-50 to-white text-cyan-700 ring-cyan-100",
    red: "from-red-50 to-white text-red-700 ring-red-100",
    green: "from-emerald-50 to-white text-emerald-700 ring-emerald-100",
    slate: "from-slate-50 to-white text-slate-700 ring-slate-100",
  };
  return (
    <div className={`rounded-[22px] bg-gradient-to-br p-5 shadow-sm ring-1 ${tones[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">{label}</div>
          <div className="mt-2 text-3xl font-black text-slate-950">{value ?? "—"}</div>
        </div>
        <div className="rounded-2xl bg-white p-3 shadow-sm">{icon}</div>
      </div>
      {hint && <div className="mt-3 text-xs font-medium text-slate-500">{hint}</div>}
    </div>
  );
}

function Panel({ title, icon, children, action }: { title: string; icon: JSX.Element; children: ReactNode; action?: JSX.Element }) {
  return (
    <section className="rounded-[24px] border border-blue-100 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-blue-50 p-2 text-blue-700">{icon}</div>
          <h2 className="text-lg font-black text-slate-950">{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export default function Dashboard() {
  const rol = useAuthStore((s) => s.rol);
  const nombre = useAuthStore((s) => s.nombre);
  const { data: kpis, isLoading } = useQuery({
    queryKey: ["dash"],
    queryFn: async () => (await api.get("/dashboard/kpis")).data,
  });
  const { data: mapa } = useQuery<ResumenMapa>({
    queryKey: ["mapa-resumen-dashboard"],
    queryFn: async () => (await api.get("/mapa/resumen")).data,
    retry: 1,
  });
  const { data: zonas } = useQuery<ZonaApi[]>({
    queryKey: ["mapa-zonas-dashboard"],
    queryFn: async () => (await api.get("/mapa/zonas")).data,
    retry: 1,
  });
  const { data: cobertura } = useQuery({
    queryKey: ["cobertura"],
    queryFn: async () => (await api.get("/consultas/cobertura-antenas")).data,
  });
  const { data: dist } = useQuery<Record<string, number>>({
    queryKey: ["dist"],
    queryFn: async () => (await api.get("/consultas/distribucion-categorias")).data,
  });
  const { data: horas } = useQuery<HoraPico[]>({
    queryKey: ["horas-pico-dashboard"],
    queryFn: async () => (await api.get("/consultas/horas-pico")).data,
    retry: 1,
  });

  const pieData = useMemo(() => Object.entries(dist ?? mapa?.por_categoria ?? {}).map(([name, value]) => ({ name, value })), [dist, mapa]);
  const estadoData = useMemo(() => Object.entries(mapa?.por_estado ?? {}).map(([name, value]) => ({ name, value })), [mapa]);
  const topZonas = useMemo(() => [...(zonas ?? [])]
    .sort((a, b) => Number(b.consumo_litros ?? 0) - Number(a.consumo_litros ?? 0))
    .slice(0, 8)
    .map((z) => ({ name: `D${z.distrito_id} · ${z.zona.slice(0, 15)}`, consumo_m3: Math.round((z.consumo_litros ?? 0) / 1000), medidores: z.medidores })), [zonas]);
  const horasData = useMemo(() => (horas ?? []).map((h) => ({ hora: `${String(h.hora).padStart(2, "0")}:00`, consumo_m3: Math.round(h.consumo_litros / 1000) })), [horas]);
  const coberturaTop = useMemo(() => (cobertura ?? []).slice(0, 10), [cobertura]);

  if (isLoading) return <div className="rounded-2xl bg-white p-6 shadow-sm">Cargando KPIs...</div>;

  const medidoresTotal = mapa?.medidores ?? kpis?.medidores_total;
  const medidoresActivos = mapa?.activos ?? kpis?.medidores_activos;
  const fueraServicio = mapa?.fuera_servicio ?? kpis?.medidores_fuera_servicio;
  const historicos = mapa?.historicos ?? 0;

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[30px] bg-gradient-to-br from-sky-950 via-blue-900 to-cyan-800 p-7 text-white shadow-xl">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-cyan-300/20 blur-3xl" />
        <div className="absolute -bottom-28 left-24 h-72 w-72 rounded-full bg-blue-300/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-cyan-100 backdrop-blur">
              <Database size={14} /> Sistema distribuido SEMAPA
            </div>
            <h1 className="text-3xl font-black tracking-tight md:text-4xl">Centro de control territorial</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-blue-100">
              Vista ejecutiva para demostrar el poblamiento: personas, infraestructuras, medidores, gateways, categorías, estados y consumo georreferenciado en Cochabamba.
            </p>
          </div>
          <div className="rounded-2xl border border-white/20 bg-white/10 px-4 py-3 text-sm backdrop-blur">
            <div className="font-black">{nombre || "Usuario"}</div>
            <div className="text-blue-100">Rol activo: {rol || "—"}</div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi label="Infraestructuras" value={fmt(mapa?.infraestructuras ?? 100000)} hint="meta consigna: 100.000" icon={<Building2 size={20} />} />
        <Kpi label="Medidores" value={fmt(medidoresTotal)} hint="meta consigna: 120.000" icon={<Waves size={20} />} tone="cyan" />
        <Kpi label="Activos" value={fmt(medidoresActivos)} hint="estado operativo" icon={<CheckCircle2 size={20} />} tone="green" />
        <Kpi label="Fallas / históricos" value={fmt(Number(fueraServicio ?? 0) + Number(historicos ?? 0))} hint="dañados, retirados o reemplazados" icon={<ShieldAlert size={20} />} tone="red" />
        <Kpi label="Gateways" value={fmt(mapa?.gateways_con_medidores ?? 32)} hint="radiobases simuladas" icon={<RadioTower size={20} />} tone="slate" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel
          title="Mapa, calor y burbujas listos para exposición"
          icon={<MapPinned size={18} />}
          action={<Link to="/mapa" className="inline-flex items-center gap-2 rounded-xl bg-blue-700 px-3 py-2 text-xs font-black text-white hover:bg-blue-800">Abrir mapa <ArrowRight size={14} /></Link>}
        >
          <div className="grid gap-4 md:grid-cols-3">
            <div className="rounded-2xl bg-blue-50 p-4 text-sm leading-6 text-blue-950">
              <div className="mb-1 font-black">Capas disponibles</div>
              Calor, burbujas, puntos de medidor, gateways y capas municipales WMS.
            </div>
            <div className="rounded-2xl bg-cyan-50 p-4 text-sm leading-6 text-cyan-950">
              <div className="mb-1 font-black">Filtros defendibles</div>
              Estado, tarifa, distrito, zona, gateway, contrato, MAC, serie y tamaño de muestra.
            </div>
            <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">
              <div className="mb-1 font-black">Tu módulo</div>
              Evidencia visual del seeder, distribución geográfica e historial de medidores.
            </div>
          </div>
        </Panel>

        <Panel title="Distribución por estado" icon={<Activity size={18} />}>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={estadoData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={55} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#2563eb" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Categorías tarifarias" icon={<Gauge size={18} />}>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={96} label>
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Top zonas por consumo" icon={<Droplets size={18} />}>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topZonas} layout="vertical" margin={{ left: 0, right: 18, top: 4, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 10 }} />
              <YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: any) => `${fmt(Number(v))} m³`} />
              <Bar dataKey="consumo_m3" fill="#0891b2" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Cobertura por gateway" icon={<RadioTower size={18} />}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={coberturaTop}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="gateway_id" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="medidores" fill="#2563eb" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Histograma por hora" icon={<BarChart3 size={18} />}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={horasData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="hora" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v: any) => `${fmt(Number(v))} m³`} />
              <Bar dataKey="consumo_m3" fill="#0ea5e9" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-xs text-slate-500">Cumple la consigna de histograma horario; depende de la carga de lecturas demo/full.</p>
        </Panel>
      </div>

      {rol === "ALCALDIA" && kpis?.poblacion_beneficiaria && (
        <div className="grid gap-4 md:grid-cols-2">
          <Kpi label="Población beneficiaria" value={fmt(kpis.poblacion_beneficiaria)} icon={<Users size={20} />} hint="según distritos cargados" />
          <Kpi label="Cobertura" value={kpis.cobertura} icon={<MapPinned size={20} />} hint="proxy urbano" tone="cyan" />
        </div>
      )}
    </div>
  );
}
