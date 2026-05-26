import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import {
  Activity,
  BarChart3,
  Building2,
  CheckCircle2,
  Database,
  DollarSign,
  Droplets,
  Gauge,
  MapPinned,
  RadioTower,
  ShieldAlert,
  Smartphone,
  TrendingUp,
  Users,
  Waves,
  Zap,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

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

type HeatmapZona = {
  zona_id: number;
  zona_nombre: string;
  distrito_id: number;
  latitud: number;
  longitud: number;
  consumo_total_litros_mes: number;
  poblacion_estimada: number;
  consumo_per_capita_litros_dia: number;
  alerta_sobreconsumo: boolean;
  color: string;
};

type AlcaldiaData = {
  heatmap: HeatmapZona[];
  umbral_litros_dia: number;
  kpis: {
    poblacion_beneficiaria: number;
    medidores_totales: number;
    medidores_activos: number;
    cobertura_servicio: number;
    consumo_total_m3: number;
    consumo_per_capita_litros: number;
    ods_6_cobertura: number;
    ods_11_desigualdad_hidrica: number;
    nuevas_conexiones_mes: number;
  };
};

const COLORS = ["#2563eb", "#0891b2", "#0ea5e9", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#64748b", "#14b8a6"];
const fmt = (n: number | undefined | null) => Number(n ?? 0).toLocaleString("es-BO");

const NIVELES_CONSUMO = [
  { nivel: 1, rango: "0 – 100 L/día", clasificacion: "Consumo ejemplar y consciente", color: "#22c55e", interpretacion: "Uso altamente eficiente y sostenible." },
  { nivel: 2, rango: "101 – 180 L/día", clasificacion: "Consumo responsable", color: "#84cc16", interpretacion: "Uso adecuado con pequeñas oportunidades de mejora." },
  { nivel: 3, rango: "181 – 250 L/día", clasificacion: "Consumo moderado", color: "#eab308", interpretacion: "Consumo aceptable, con señales de exceso." },
  { nivel: 4, rango: "251 – 300 L/día", clasificacion: "Consumo elevado", color: "#f97316", interpretacion: "Cercano al límite crítico." },
  { nivel: 5, rango: "301 – 400 L/día", clasificacion: "Consumo inconsciente", color: "#ef4444", interpretacion: "Exceso evidente, desperdicio significativo." },
  { nivel: 6, rango: "Más de 400 L/día", clasificacion: "Consumo crítico e insostenible", color: "#b91c1c", interpretacion: "Nivel alarmante de desperdicio." },
];

function KpiCard({ label, value, hint, icon, tone = "blue" }: { label: string; value: any; hint?: string; icon: JSX.Element; tone?: "blue" | "cyan" | "red" | "green" | "slate" | "amber" }) {
  const tones: Record<string, string> = {
    blue: "from-blue-50 to-white text-blue-700 ring-blue-100",
    cyan: "from-cyan-50 to-white text-cyan-700 ring-cyan-100",
    red: "from-red-50 to-white text-red-700 ring-red-100",
    green: "from-emerald-50 to-white text-emerald-700 ring-emerald-100",
    slate: "from-slate-50 to-white text-slate-700 ring-slate-100",
    amber: "from-amber-50 to-white text-amber-700 ring-amber-100",
  };
  return (
    <div className={`group relative overflow-hidden rounded-2xl bg-gradient-to-br p-5 shadow-md transition-all hover:scale-[1.02] hover:shadow-xl ring-1 ${tones[tone]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="z-10">
          <div className="text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">{label}</div>
          <div className="mt-2 text-3xl font-black text-slate-950">{value ?? "—"}</div>
          {hint && <div className="mt-3 text-xs font-medium text-slate-500">{hint}</div>}
        </div>
        <div className="rounded-2xl bg-white/80 p-3 shadow-sm backdrop-blur-sm transition-transform group-hover:rotate-3">{icon}</div>
      </div>
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-current opacity-5" />
    </div>
  );
}

function Panel({ title, icon, children, action }: { title: string; icon: JSX.Element; children: ReactNode; action?: JSX.Element }) {
  return (
    <section className="rounded-2xl border border-blue-100 bg-white p-5 shadow-sm transition-all hover:shadow-md">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-blue-50 p-2 text-blue-700">{icon}</div>
          <h2 className="text-lg font-black text-slate-950">{title}</h2>
        </div>
        {action && <div>{action}</div>}
      </div>
      {children}
    </section>
  );
}

export default function Dashboard() {
  const rol = useAuthStore((s) => s.rol);
  const nombre = useAuthStore((s) => s.nombre);
  const [selectedZone, setSelectedZone] = useState<HeatmapZona | null>(null);

  const { data: kpis, isLoading: kpisLoading } = useQuery({
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

  const { data: alcaldia, isLoading: alcaldiaLoading } = useQuery<AlcaldiaData>({
    queryKey: ["alcaldia-dashboard"],
    queryFn: async () => (await api.get("/dashboard/alcaldia")).data,
    enabled: rol === "ALCALDIA",
  });

  const pieData = useMemo(() => Object.entries(mapa?.por_categoria ?? {}).map(([name, value]) => ({ name, value })), [mapa]);
  const estadoData = useMemo(() => Object.entries(mapa?.por_estado ?? {}).map(([name, value]) => ({ name, value })), [mapa]);
  const topZonas = useMemo(() => [...(zonas ?? [])].sort((a, b) => Number(b.consumo_litros ?? 0) - Number(a.consumo_litros ?? 0)).slice(0, 8).map((z) => ({ name: `D${z.distrito_id} · ${z.zona.slice(0, 20)}`, consumo_m3: Math.round((z.consumo_litros ?? 0) / 1000), medidores: z.medidores })), [zonas]);

  const medidoresTotal = mapa?.medidores ?? kpis?.medidores_total ?? 0;
  const medidoresActivos = mapa?.activos ?? kpis?.medidores_activos ?? 0;
  const fueraServicio = mapa?.fuera_servicio ?? kpis?.medidores_fuera_servicio ?? 0;
  const historicos = mapa?.historicos ?? 0;

  if (kpisLoading) return <div className="flex h-96 items-center justify-center rounded-2xl bg-white p-6 shadow-sm">Cargando indicadores clave...</div>;

  return (
    <div className="space-y-6">
      <header className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-sky-950 via-blue-900 to-cyan-800 p-7 text-white shadow-xl">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-cyan-300/20 blur-3xl" />
        <div className="absolute -bottom-28 left-24 h-72 w-72 rounded-full bg-blue-300/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-cyan-100 backdrop-blur">
              <Database size={14} /> Sistema distribuido SEMAPA
            </div>
            <h1 className="text-3xl font-black tracking-tight md:text-4xl">Centro de control territorial</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-blue-100">Visualización ejecutiva con indicadores estratégicos, análisis de consumo sostenible y mapa de calor georreferenciado.</p>
          </div>
          <div className="rounded-2xl border border-white/20 bg-white/10 px-4 py-3 text-sm backdrop-blur">
            <div className="font-black">{nombre || "Usuario"}</div>
            <div className="text-blue-100">Rol activo: {rol || "—"}</div>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <KpiCard label="Infraestructuras" value={fmt(mapa?.infraestructuras ?? 80000)} hint="Meta: 100.000" icon={<Building2 size={20} />} />
        <KpiCard label="Medidores" value={fmt(medidoresTotal)} hint="Meta: 120.000" icon={<Waves size={20} />} tone="cyan" />
        <KpiCard label="Activos" value={fmt(medidoresActivos)} hint="Operativos" icon={<CheckCircle2 size={20} />} tone="green" />
        <KpiCard label="Fallas / históricos" value={fmt(fueraServicio + historicos)} hint="Dañados, retirados" icon={<ShieldAlert size={20} />} tone="red" />
        <KpiCard label="Gateways" value={fmt(mapa?.gateways_con_medidores ?? 14)} hint="Radiobases LoRaWAN" icon={<RadioTower size={20} />} tone="slate" />
        {rol === "ALCALDIA" && alcaldia?.kpis && <KpiCard label="Cobertura de servicio" value={`${alcaldia.kpis.cobertura_servicio}%`} hint="ODS 6" icon={<Users size={20} />} tone="amber" />}
      </div>

      {rol === "ALCALDIA" && (
        <div className="grid gap-5 xl:grid-cols-[1.4fr_0.6fr]">
          <Panel title="Mapa de calor por zona – Consumo per cápita" icon={<MapPinned size={18} />} action={<div className="rounded-full bg-blue-100 px-3 py-1 text-xs font-black text-blue-800">Umbral: {alcaldia?.umbral_litros_dia ?? 300} L/persona/día</div>}>
            {alcaldiaLoading ? (
              <div className="flex h-96 items-center justify-center">Cargando mapa de calor...</div>
            ) : alcaldia?.heatmap && alcaldia.heatmap.length > 0 ? (
              <>
                <MapContainer center={[-17.3895, -66.1568]} zoom={12} style={{ height: "420px", width: "100%", borderRadius: "1rem", zIndex: 1 }} className="shadow-md">
                  <TileLayer url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CartoDB' />
                  {alcaldia.heatmap.map((zona) => (
                    <CircleMarker key={zona.zona_id} center={[zona.latitud, zona.longitud]} radius={Math.min(28, Math.sqrt(zona.consumo_total_litros_mes / 50000) + 8)} fillColor={zona.color} color="white" weight={1.5} fillOpacity={0.75} eventHandlers={{ click: () => setSelectedZone(zona), mouseover: (e) => e.target.openPopup() }}>
                      <Popup>
                        <div className="text-sm">
                          <div className="font-black text-slate-900">{zona.zona_nombre}</div>
                          <div className="text-slate-500">Distrito {zona.distrito_id}</div>
                          <hr className="my-1" />
                          <div><b>Consumo total:</b> {(zona.consumo_total_litros_mes / 1000).toFixed(0)} m³</div>
                          <div><b>Población:</b> {zona.poblacion_estimada.toLocaleString()} hab.</div>
                          <div className={`font-bold ${zona.alerta_sobreconsumo ? "text-red-600" : "text-green-600"}`}>Consumo per cápita: {zona.consumo_per_capita_litros_dia} L/día</div>
                          {zona.alerta_sobreconsumo && <div className="mt-1 text-red-500">⚠️ Supera el umbral recomendado</div>}
                        </div>
                      </Popup>
                    </CircleMarker>
                  ))}
                </MapContainer>
                <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <h3 className="mb-2 text-sm font-black text-slate-800">📊 Niveles de consumo diario por persona</h3>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-100 text-left font-bold text-slate-700">
                        <th className="px-2 py-1">Nivel</th><th className="px-2 py-1">Rango (L/día)</th><th className="px-2 py-1">Clasificación</th><th className="px-2 py-1">Color</th><th className="px-2 py-1">Interpretación</th>
                      </tr>
                    </thead>
                    <tbody>
                      {NIVELES_CONSUMO.map((n) => (
                        <tr key={n.nivel} className="border-t border-slate-200 hover:bg-white">
                          <td className="px-2 py-1.5 font-bold">{n.nivel}</td><td className="px-2 py-1.5">{n.rango}</td><td className="px-2 py-1.5 italic">{n.clasificacion}</td><td className="px-2 py-1.5"><div className="h-4 w-6 rounded" style={{ backgroundColor: n.color }} /></td><td className="px-2 py-1.5 text-slate-600">{n.interpretacion}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="flex h-64 items-center justify-center rounded-2xl bg-slate-50 text-slate-400">No hay datos de calor para el período seleccionado</div>
            )}
          </Panel>
          <Panel title="Objetivos de Desarrollo Sostenible" icon={<Gauge size={18} />}>
            {alcaldia?.kpis ? (
              <div className="space-y-4">
                <div className="rounded-xl bg-blue-50 p-4"><div className="text-xs font-black uppercase text-blue-700">ODS 6 – Agua limpia</div><div className="mt-1 text-2xl font-black">{alcaldia.kpis.ods_6_cobertura}%</div><div className="text-sm">Cobertura de agua potable</div></div>
                <div className="rounded-xl bg-cyan-50 p-4"><div className="text-xs font-black uppercase text-cyan-700">ODS 11 – Ciudades sostenibles</div><div className="mt-1 text-2xl font-black">{alcaldia.kpis.ods_11_desigualdad_hidrica}</div><div className="text-sm">Índice de desigualdad hídrica</div></div>
                <div className="rounded-xl bg-emerald-50 p-4"><div className="text-xs font-black uppercase text-emerald-700">Nuevas conexiones</div><div className="mt-1 text-2xl font-black">{alcaldia.kpis.nuevas_conexiones_mes}</div><div className="text-sm">Contratos activados en el mes</div></div>
              </div>
            ) : (
              <div className="text-center text-slate-400">Cargando ODS...</div>
            )}
          </Panel>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Distribución por estado" icon={<Activity size={18} />}>
          {estadoData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={estadoData} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" tick={{ fontSize: 10 }} /><YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 10 }} /><RechartsTooltip /><Bar dataKey="value" fill="#2563eb" radius={[0, 8, 8, 0]} /></BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-40 items-center justify-center text-slate-400">Sin datos de estado</div>
          )}
        </Panel>
        <Panel title="Categorías tarifarias" icon={<Gauge size={18} />}>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}><PieChart><Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={96} label>{pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><RechartsTooltip /></PieChart></ResponsiveContainer>
          ) : (
            <div className="flex h-40 items-center justify-center text-slate-400">Sin datos de categorías</div>
          )}
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Top zonas por consumo" icon={<Droplets size={18} />}>
          <ResponsiveContainer width="100%" height={280}><BarChart data={topZonas} layout="vertical" margin={{ left: 0, right: 18 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} /><XAxis type="number" tick={{ fontSize: 10 }} /><YAxis type="category" dataKey="name" width={130} tick={{ fontSize: 10 }} /><RechartsTooltip formatter={(v: any) => `${fmt(Number(v))} m³`} /><Bar dataKey="consumo_m3" fill="#0891b2" radius={[0, 8, 8, 0]} /></BarChart></ResponsiveContainer>
        </Panel>
        <Panel title="Cobertura por gateway" icon={<RadioTower size={18} />}>
          <div className="flex h-40 items-center justify-center text-slate-400">Datos no disponibles</div>
        </Panel>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Histograma por hora" icon={<BarChart3 size={18} />}>
          <div className="flex h-40 items-center justify-center text-slate-400">Datos no disponibles</div>
          <p className="mt-2 text-xs text-slate-500">Distribución horaria del consumo a partir de lecturas IoT.</p>
        </Panel>

        {rol === "GERENCIA" && kpis && (
          <Panel title="Indicadores de gestión" icon={<Zap size={18} />}>
            <div className="grid grid-cols-2 gap-4">
              <KpiCard label="Consumo total" value={`${fmt(kpis.consumo_total_m3)} m³`} icon={<Zap size={16} />} tone="cyan" />
              <KpiCard label="Pico máximo horario" value={`${fmt(kpis.pico_maximo_horario_m3)} m³`} icon={<TrendingUp size={16} />} tone="amber" />
              <KpiCard label="Lecturas app móvil" value={fmt(kpis.lecturas_app_movil)} icon={<Smartphone size={16} />} tone="green" />
            </div>
          </Panel>
        )}

        {rol === "CONTABILIDAD" && kpis && (
          <Panel title="Resumen financiero" icon={<DollarSign size={18} />}>
            <div className="grid grid-cols-2 gap-4">
              <KpiCard label="Facturado (Bs)" value={fmt(kpis.monto_facturado_bs)} icon={<DollarSign size={16} />} tone="green" />
              <KpiCard label="Recaudado (Bs)" value={fmt(kpis.monto_recaudado_bs)} icon={<CheckCircle2 size={16} />} tone="cyan" />
              <KpiCard label="Cartera vencida" value={fmt(kpis.cartera_vencida_bs)} icon={<ShieldAlert size={16} />} tone="red" />
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}