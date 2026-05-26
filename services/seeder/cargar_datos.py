"""
carga_total.py — Carga todo en 2-3 minutos con execute_concurrent_with_args.
Sin batches, sin bucles lentos.
"""

import csv, os, glob, uuid, time
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent_with_args

HOSTS = os.getenv("CASSANDRA_HOSTS", "127.0.0.1").split(",")
PORT = int(os.getenv("CASSANDRA_PORT", "9042"))
KS = os.getenv("CASSANDRA_KEYSPACE", "semapa")

cluster = Cluster(contact_points=HOSTS, port=PORT, protocol_version=4)
session = cluster.connect(KS)
print("✅ Conectado")

def find_csv(pats):
    for p in pats:
        for path in glob.glob(f"data/resources/{p}") + glob.glob(f"data/{p}") + glob.glob(p):
            return path
    raise FileNotFoundError(f"No encontrado: {pats}")

def open_csv_safe(path):
    for enc in ["latin-1","utf-8-sig","utf-8","cp1252"]:
        try:
            f = open(path, "r", encoding=enc, newline="")
            r = csv.DictReader(f); next(r); f.seek(0)
            return f, csv.DictReader(f)
        except: 
            try: f.close()
            except: pass
    raise RuntimeError(f"No se pudo leer {path}")

def sint(v,d=1):
    try: return int(float(str(v).strip()))
    except: return d

def sfloat(v,d=0.0):
    try: return float(str(v).strip())
    except: return d

def sdate(v):
    for f in ("%Y-%m-%d","%m/%d/%y","%m/%d/%Y","%d/%m/%Y"):
        try: return datetime.strptime(str(v).strip(),f).date()
        except: pass
    return None

def contrato_to_int(v):
    s = str(v).strip()
    if s.upper().startswith("CT-"):
        s = s.split("-", 1)[1] if "-" in s else s[3:]
    return int(s) if s.isdigit() else 0

def bulk_insert(ps, tuples_list, desc):
    """Inserta con execute_concurrent_with_args, ignorando errores."""
    results = execute_concurrent_with_args(session, ps, tuples_list, concurrency=100, raise_on_first_error=False)
    ok = sum(1 for success, _ in results if success)
    err = len(tuples_list) - ok
    if err: print(f"   ⚠️  {desc}: {err} errores de {len(tuples_list)}")
    return ok

now = datetime.utcnow()
CHUNK = 5000  # procesar de a 5000 filas

# ── 1. INFRAESTRUCTURAS ──
t0 = time.time()
print("\n📌 Infraestructuras...")
session.execute("TRUNCATE infraestructuras")
ps = session.prepare("INSERT INTO infraestructuras (infraestructura_id, persona_id, tipo_infra, distrito_id, zona_id, direccion, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
f, r = open_csv_safe(find_csv(["*infraestructuras*.csv"]))
chunk, total = [], 0
for row in r:
    chunk.append((uuid.uuid4(), uuid.uuid4(), 1, sint(row.get("distrito")), 1, str(row.get("direccion","")).strip(), sfloat(row.get("latitud"),-17.3895), sfloat(row.get("longitud"),-66.1568)))
    if len(chunk) >= CHUNK:
        total += bulk_insert(ps, chunk, "infraestructuras")
        chunk.clear()
        print(f"   {total:,}", end="\r")
if chunk: total += bulk_insert(ps, chunk, "infraestructuras")
f.close()
print(f"\n   ✅ {total:,} ({time.time()-t0:.1f}s)")

# ── 2. MEDIDORES ──
t0 = time.time()
print("\n📌 Medidores...")
session.execute("TRUNCATE medidores")
ps = session.prepare("INSERT INTO medidores (medidor_id, mac, numero_serie, modelo_id, categoria_tarifa, gateway_id, distrito_id, zona_id, fecha_instalacion, estado, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
EM = {"Operativo":"ACTIVO","Reacondicionado":"ACTIVO","Dañado":"FUERA_SERVICIO","Mantenimiento":"MANTENIMIENTO"}
f, r = open_csv_safe(find_csv(["*medidores*.csv"]))
chunk, total = [], 0
for row in r:
    iot = str(row.get("medidor_iot","")).strip()
    if not iot: continue
    chunk.append((uuid.uuid4(), iot.replace(":",""), f"SN-{iot.replace(':','')[:10]}", sint(row.get("tipo_medidor_id")), "R3", 1, 1, 1, sdate(row.get("fecha_instalacion")), EM.get(str(row.get("estado","")).strip(),"ACTIVO"), sfloat(row.get("latitud",-17.3895)), sfloat(row.get("longitud",-66.1568))))
    if len(chunk) >= CHUNK:
        total += bulk_insert(ps, chunk, "medidores")
        chunk.clear()
        print(f"   {total:,}", end="\r")
if chunk: total += bulk_insert(ps, chunk, "medidores")
f.close()
print(f"\n   ✅ {total:,} ({time.time()-t0:.1f}s)")

# ── 3. CONTRATOS ──
t0 = time.time()
print("\n📌 Contratos...")
session.execute("TRUNCATE contratos")
ps = session.prepare("INSERT INTO contratos (numero_contrato, numero_catastro, ci_titular, categoria, subcategoria, medidor_iot, fecha_contrato, estado_contrato, diametro_conexion, tipo_servicio, fecha_carga) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
EC = {"ACTIVO":"ACTIVO","MOROSO":"MORA","CORTADO":"SUSPENDIDO","SUSPENDIDO":"SUSPENDIDO"}
f, r = open_csv_safe(find_csv(["*contratos*.csv"]))
chunk, total = [], 0
for row in r:
    nc_str = str(row.get("numero_contrato","")).strip()
    if not nc_str: continue
    nc_int = contrato_to_int(nc_str)
    if nc_int == 0: continue
    chunk.append((nc_int, str(row.get("numero_catastro","")).strip(), str(row.get("ci_titular","")).strip(), str(row.get("categoria","Residencial")).strip(), str(row.get("subcategoria","R2")).strip(), str(row.get("medidor_iot","")).strip(), sdate(row.get("fecha_contrato")), EC.get(str(row.get("estado_contrato","")).strip().upper(),"ACTIVO"), str(row.get("diametro_conexion",'1/2"')).strip(), str(row.get("tipo_servicio","Agua Potable")).strip(), now))
    if len(chunk) >= CHUNK:
        total += bulk_insert(ps, chunk, "contratos")
        chunk.clear()
        print(f"   {total:,}", end="\r")
if chunk: total += bulk_insert(ps, chunk, "contratos")
f.close()
print(f"\n   ✅ {total:,} ({time.time()-t0:.1f}s)")

# ── 4. FACTURAS ──
t0 = time.time()
print("\n📌 Facturas...")
session.execute("TRUNCATE facturas")
ps = session.prepare("INSERT INTO facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
med_a_con = {r.medidor_iot: r.numero_contrato for r in session.execute("SELECT medidor_iot, numero_contrato FROM contratos") if r.medidor_iot}
f, r = open_csv_safe(find_csv(["*lecturas*.csv"]))
chunk, total = [], 0
for row in r:
    iot = str(row.get("medidor_iot","")).strip()
    if not iot: continue
    c = max(0, sfloat(row.get("LecturaActual")) - sfloat(row.get("lecturaAnterior")))
    nc = med_a_con.get(iot)
    if not nc: continue
    chunk.append((nc, "2026-05", uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), c, round(c*0.5,2), round(c*0.5*6.96,2), 6.96, "R3", '{"periodo":"2026-05"}', now, "PAGADA"))
    if len(chunk) >= CHUNK:
        total += bulk_insert(ps, chunk, "facturas")
        chunk.clear()
        print(f"   {total:,}", end="\r")
if chunk: total += bulk_insert(ps, chunk, "facturas")
f.close()
print(f"\n   ✅ {total:,} ({time.time()-t0:.1f}s)")

# ── RESUMEN ──
print("\n📊 RESUMEN")
for t in ["infraestructuras", "medidores", "contratos", "facturas"]:
    try: print(f"   ✅ {t}: {session.execute(f'SELECT COUNT(*) FROM {t}').one().count:,}")
    except: print(f"   ❌ {t}")

session.shutdown(); cluster.shutdown()
print(f"\n🎉 ¡LISTO en {time.time()-t0:.0f}s! docker-compose build --no-cache api-1 api-2 web && docker-compose up -d")