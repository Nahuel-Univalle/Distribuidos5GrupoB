import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuthStore } from "../store/auth";
import { Database, Droplet, Lock, MapPinned, User } from "lucide-react";

export default function Login() {
  const [username, setU] = useState("alcaldia");
  const [password, setP] = useState("Alcaldia2025!");
  const [err, setErr] = useState("");
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try {
      const r = await api.post("/auth/login", { username, password });
      login(r.data.access_token, r.data.rol, r.data.nombre);
      navigate("/");
    } catch (e: any) {
      setErr(e.response?.data?.detail || "Error de autenticación");
    }
  }

  return (
    <div className="relative min-h-full overflow-hidden bg-slate-950">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,.35),transparent_35%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,.28),transparent_32%)]" />
      <div className="absolute inset-x-0 top-0 h-48 bg-gradient-to-b from-blue-500/10 to-transparent" />
      <div className="relative grid min-h-screen place-items-center p-6">
        <div className="grid w-full max-w-5xl overflow-hidden rounded-[34px] border border-white/10 bg-white shadow-2xl lg:grid-cols-[1.05fr_0.95fr]">
          <section className="relative hidden bg-gradient-to-br from-sky-950 via-blue-950 to-cyan-900 p-10 text-white lg:block">
            <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-cyan-300/20 blur-3xl" />
            <div className="relative">
              <div className="mb-10 inline-flex items-center gap-3 rounded-3xl bg-white/10 p-3 backdrop-blur">
                <Droplet className="text-cyan-200" size={34} />
                <div>
                  <div className="text-2xl font-black">SEMAPA</div>
                  <div className="text-xs font-bold uppercase tracking-[0.18em] text-cyan-100">Agua Inteligente</div>
                </div>
              </div>
              <h1 className="text-4xl font-black leading-tight">Gestión distribuida de agua potable para Cochabamba</h1>
              <p className="mt-4 max-w-md text-sm leading-7 text-blue-100">
                Cassandra, IoT LoRaWAN, georreferenciación, dashboard, facturación y mensajería en una arquitectura de servicios.
              </p>
              <div className="mt-10 grid gap-3">
                <div className="rounded-2xl bg-white/10 p-4 backdrop-blur"><Database className="mb-2 text-cyan-200" size={20} /><b>120.000 medidores</b><br/><span className="text-sm text-blue-100">datos masivos para consultas estratégicas</span></div>
                <div className="rounded-2xl bg-white/10 p-4 backdrop-blur"><MapPinned className="mb-2 text-cyan-200" size={20} /><b>Mapa territorial</b><br/><span className="text-sm text-blue-100">calor, burbujas, gateways y filtros</span></div>
              </div>
            </div>
          </section>

          <form onSubmit={submit} className="p-8 md:p-12">
            <div className="mb-8 lg:hidden">
              <div className="flex items-center gap-3">
                <Droplet className="text-blue-700" size={32} />
                <div>
                  <h1 className="text-2xl font-black text-blue-950">SEMAPA</h1>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-blue-600">Agua Inteligente</p>
                </div>
              </div>
            </div>
            <div className="mb-8">
              <h2 className="text-3xl font-black text-slate-950">Ingresar al sistema</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">Usa un rol de prueba para revisar el dashboard y el mapa georreferenciado.</p>
            </div>

            <label className="mb-2 block text-xs font-black uppercase tracking-[0.16em] text-slate-500">Usuario</label>
            <div className="mb-4 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus-within:border-blue-300 focus-within:bg-white">
              <User size={18} className="text-slate-400" />
              <input className="w-full bg-transparent text-sm outline-none" value={username} onChange={(e) => setU(e.target.value)} />
            </div>

            <label className="mb-2 block text-xs font-black uppercase tracking-[0.16em] text-slate-500">Contraseña</label>
            <div className="mb-4 flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 focus-within:border-blue-300 focus-within:bg-white">
              <Lock size={18} className="text-slate-400" />
              <input type="password" className="w-full bg-transparent text-sm outline-none" value={password} onChange={(e) => setP(e.target.value)} />
            </div>

            {err && <div className="mb-4 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-700">{err}</div>}
            <button className="w-full rounded-2xl bg-blue-700 py-3 font-black text-white shadow-lg shadow-blue-700/20 hover:bg-blue-800">
              Ingresar
            </button>
            <div className="mt-5 rounded-2xl bg-blue-50 p-4 text-xs leading-6 text-blue-950">
              <b>Roles disponibles:</b> alcaldia / Alcaldia2025! · gerencia / Gerencia2025! · contabilidad / Contab2025!
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
