"""SEMAPA — Seeder de lecturas históricas (time-series).

IMPORTANTE PARA LA DEMO
-----------------------
La carga completa real puede superar 100 millones de lecturas si se ejecuta desde
2025-04-01 hasta la fecha actual, con 3 lecturas diarias y todos los medidores.
Eso es correcto para una carga masiva, pero no es práctico en una laptop durante
la defensa.

Por eso este archivo trae presets:

  LECTURAS_PRESET=demo        -> default. Carga rápida para dashboard/API/mapa.
  LECTURAS_PRESET=exposicion  -> muestra más grande, todavía razonable.
  LECTURAS_PRESET=full        -> carga completa; requiere confirmación explícita.
  LECTURAS_PRESET=custom      -> usa solamente variables de entorno manuales.

Comandos:

  # Rápido, recomendado para defensa
  docker compose run --rm seeder python seed_lecturas.py

  # Otra forma explícita
  docker compose run --rm -e LECTURAS_PRESET=demo seeder python seed_lecturas.py

  # Carga completa, muy lenta y pesada
  docker compose run --rm -e LECTURAS_PRESET=full -e LECTURAS_CONFIRMAR_FULL=SI seeder python seed_lecturas.py

Tablas escritas:
  - lecturas_por_medidor   PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)
  - lecturas_por_zona_dia  PRIMARY KEY ((distrito_id, zona_id, fecha), hora, medidor_id)

La carga demo mantiene la misma lógica de negocio:
  - fechas desde 2025-04-01,
  - franjas horarias de consumo,
  - errores IoT 0.5%,
  - manuales 5%,
  - consumo residencial distinto por horario,
  - datos repartidos por zonas/tarifas usando muestreo estratificado.
"""
from __future__ import annotations

import os
import random
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from loguru import logger
from tqdm import tqdm

from cassandra_io import bulk_insert, connect

# Las plantillas de la hoja Lecturas del XLSX nuevo no reemplazan la generación
# masiva, pero se usan para inicializar acumulados y validar formato esperado.
try:
    from excel_loader import load_workbook, load_lecturas_templates
except Exception:  # pragma: no cover - fallback si se ejecuta aislado
    load_workbook = None
    load_lecturas_templates = None


@dataclass(frozen=True)
class LecturasConfig:
    preset: str
    desde: date
    hasta: date
    concurrency: int
    batch: int
    limite_medidores: int
    por_dia: int
    step_dias: int
    seed: int
    max_filas: int
    confirmar_full: bool


PRESETS = {
    # Pensado para laptop / defensa. Con fecha actual 2026-05-17 genera aprox:
    # 5000 medidores x 30 días efectivos x 1 lectura = 150.000 lecturas
    # y se escriben en 2 tablas = 300.000 inserciones.
    "demo": {
        "limite_medidores": 5000,
        "por_dia": 1,
        "step_dias": 14,
        "batch": 10000,
        "concurrency": 300,
        "max_filas": 0,
    },
    # Muestra más grande, útil si se quiere enseñar más volumen sin llegar a full.
    "exposicion": {
        "limite_medidores": 12000,
        "por_dia": 1,
        "step_dias": 14,
        "batch": 12000,
        "concurrency": 300,
        "max_filas": 0,
    },
    # Carga real completa. Muy pesada.
    "full": {
        "limite_medidores": 0,
        "por_dia": 3,
        "step_dias": 1,
        "batch": 10000,
        "concurrency": 300,
        "max_filas": 0,
    },
    # Sin defaults: usa las variables manuales que definas.
    "custom": {},
}


RESIDENCIALES = {"R1", "R2", "R3", "R4"}
TODOS_BLOQUES = [12, 2, 18]  # mediodía, madrugada, tarde


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} debe ser entero; recibido={raw!r}")


def env_date(name: str, default: str) -> date:
    raw = os.getenv(name, default)
    return datetime.strptime(raw, "%Y-%m-%d").date()


def build_config() -> LecturasConfig:
    preset = os.getenv("LECTURAS_PRESET", "demo").strip().lower()
    if preset not in PRESETS:
        raise ValueError(f"LECTURAS_PRESET inválido: {preset}. Usa demo, exposicion, full o custom.")

    p = PRESETS[preset]
    desde = env_date("LECTURAS_DESDE", "2025-04-01")
    hasta = env_date("LECTURAS_HASTA", date.today().isoformat())
    if hasta < desde:
        raise ValueError("LECTURAS_HASTA no puede ser menor que LECTURAS_DESDE")

    por_dia = max(1, min(3, env_int("LECTURAS_POR_DIA", p.get("por_dia", 3))))
    step_dias = max(1, env_int("LECTURAS_STEP_DIAS", p.get("step_dias", 1)))

    return LecturasConfig(
        preset=preset,
        desde=desde,
        hasta=hasta,
        concurrency=max(1, env_int("LECTURAS_CONCURRENCY", p.get("concurrency", 200))),
        batch=max(100, env_int("LECTURAS_BATCH", p.get("batch", 5000))),
        limite_medidores=max(0, env_int("LECTURAS_LIMITE_MEDIDORES", p.get("limite_medidores", 0))),
        por_dia=por_dia,
        step_dias=step_dias,
        seed=env_int("SEED_RNG", 20250512),
        max_filas=max(0, env_int("LECTURAS_MAX_FILAS", p.get("max_filas", 0))),
        confirmar_full=os.getenv("LECTURAS_CONFIRMAR_FULL", "").strip().upper() == "SI",
    )


CFG = build_config()
EXCEL_PATH = os.getenv("SEEDER_EXCEL", "/recursos/recursos.xlsx")
random.seed(CFG.seed)
BLOQUES = TODOS_BLOQUES[: CFG.por_dia]


def cargar_plantillas_lecturas() -> list:
    if not load_workbook or not load_lecturas_templates:
        return []
    try:
        wb = load_workbook(EXCEL_PATH)
        plantillas = load_lecturas_templates(wb)
        logger.info(f"Hoja Lecturas XLSX validada: {len(plantillas)} ejemplos de formato")
        return plantillas
    except Exception as exc:
        logger.warning(f"No se pudo usar la hoja Lecturas del XLSX: {exc}")
        return []


def consumo_para(cat: str, hora_int: int) -> int:
    """Consumo diferencial realista según categoría y hora del día."""
    if cat in RESIDENCIALES:
        if hora_int < 8:
            return random.randint(0, 1300)
        if hora_int < 16:
            return random.randint(0, 380)
        return random.randint(0, 190)
    return random.randint(0, 250)


def status_para() -> int:
    r = random.random()
    if r < 0.005:  # 0.5% errores 3..9
        return random.randint(3, 9)
    if r < 0.05:  # 5% manuales
        return 2
    return 1


def sample_estratificado(rows: list[tuple], limite: int) -> list[tuple]:
    """Toma una muestra repartida por distrito/zona/tarifa.

    Evita que el demo cargue solo los primeros medidores devueltos por Cassandra.
    Así el mapa y las consultas tienen lecturas en muchas zonas y categorías.
    """
    if not limite or len(rows) <= limite:
        return rows

    grupos: dict[tuple, deque] = defaultdict(deque)
    for row in rows:
        _med_id, cat, _gw, dist_id, zona_id = row
        grupos[(dist_id, zona_id, cat)].append(row)

    seleccion: list[tuple] = []
    keys = list(grupos.keys())
    random.shuffle(keys)

    # Primera pasada: al menos 1 por grupo hasta llegar al límite.
    for k in keys:
        if len(seleccion) >= limite:
            break
        if grupos[k]:
            seleccion.append(grupos[k].popleft())

    # Relleno round-robin para mantener distribución.
    while len(seleccion) < limite:
        agregado = False
        for k in keys:
            if len(seleccion) >= limite:
                break
            if grupos[k]:
                seleccion.append(grupos[k].popleft())
                agregado = True
        if not agregado:
            break

    random.shuffle(seleccion)
    return seleccion


def fetch_medidores(session) -> list[tuple]:
    """Trae (medidor_id, categoria_tarifa, gateway_id, distrito_id, zona_id)."""
    logger.info("Cargando medidores activos actuales...")
    q = "SELECT medidor_id, categoria_tarifa, gateway_id, distrito_id, zona_id, estado FROM medidores"
    rows = []
    for r in session.execute(q):
        if r.estado != "ACTIVO":
            continue
        rows.append((r.medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id))

    total_activos = len(rows)
    rows = sample_estratificado(rows, CFG.limite_medidores)
    logger.info(f"Medidores activos encontrados: {total_activos}")
    logger.info(f"Medidores usados para esta carga ({CFG.preset}): {len(rows)}")
    return rows


def fechas() -> list[date]:
    d = CFG.desde
    out = []
    while d <= CFG.hasta:
        out.append(d)
        d += timedelta(days=CFG.step_dias)
    return out


def flush(session, ps_med, ps_zona, rows_med: list[tuple], rows_zona: list[tuple]) -> None:
    if not rows_med:
        return
    bulk_insert(session, ps_med, rows_med, concurrency=CFG.concurrency)
    bulk_insert(session, ps_zona, rows_zona, concurrency=CFG.concurrency)
    rows_med.clear()
    rows_zona.clear()


def main():
    t0 = time.time()
    cluster, session = connect()
    try:
        medidores = fetch_medidores(session)
        if not medidores:
            logger.error("No hay medidores. Ejecuta seed.py primero.")
            return

        dias = fechas()
        esperado = len(medidores) * len(dias) * CFG.por_dia

        logger.info(
            f"Preset={CFG.preset} | período {CFG.desde}..{CFG.hasta} | "
            f"días efectivos={len(dias)} (cada {CFG.step_dias} días) | "
            f"medidores={len(medidores)} | lecturas/día={CFG.por_dia} | "
            f"lecturas esperadas≈{esperado:,} | escrituras Cassandra≈{esperado*2:,}"
        )

        if CFG.preset == "full" and not CFG.confirmar_full:
            logger.error(
                "La carga FULL es muy pesada y puede tardar horas. Para ejecutarla usa: "
                "docker compose run --rm -e LECTURAS_PRESET=full -e LECTURAS_CONFIRMAR_FULL=SI "
                "seeder python seed_lecturas.py"
            )
            return

        if esperado > 5_000_000 and CFG.preset not in {"full"}:
            logger.warning(
                "Esta carga supera 5 millones de lecturas. Para defensa usa LECTURAS_PRESET=demo "
                "o reduce LECTURAS_LIMITE_MEDIDORES / LECTURAS_STEP_DIAS."
            )

        ps_med = session.prepare(
            "INSERT INTO lecturas_por_medidor (medidor_id, anio_mes, fecha_hora, gateway_id, "
            "lectura_litros, consumo_litros, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        ps_zona = session.prepare(
            "INSERT INTO lecturas_por_zona_dia (distrito_id, zona_id, fecha, hora, medidor_id, "
            "consumo_litros, categoria_tarifa) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )

        plantillas_lecturas = cargar_plantillas_lecturas()
        valores_base = [int(p.lectura_actual) for p in plantillas_lecturas if getattr(p, "lectura_actual", 0)]
        if valores_base:
            acumulado: dict[uuid.UUID, int] = {m[0]: random.choice(valores_base) * 1000 + random.randint(0, 999) for m in medidores}
        else:
            acumulado = {m[0]: random.randint(100_000, 500_000) for m in medidores}
        rows_med: list[tuple] = []
        rows_zona: list[tuple] = []
        total = 0
        stop = False

        for d in tqdm(dias, desc="dias"):
            anio_mes = d.year * 100 + d.month
            for hora_int in BLOQUES:
                ts = datetime(d.year, d.month, d.day, hora_int, 0, 0)
                for med_id, cat, gw, dist_id, zona_id in medidores:
                    c = consumo_para(cat, hora_int)
                    acumulado[med_id] += c
                    st = status_para()
                    rows_med.append((med_id, anio_mes, ts, gw, acumulado[med_id], c, st))
                    rows_zona.append((dist_id, zona_id, d, hora_int, med_id, c, cat))
                    total += 1

                    if len(rows_med) >= CFG.batch:
                        flush(session, ps_med, ps_zona, rows_med, rows_zona)

                    if CFG.max_filas and total >= CFG.max_filas:
                        stop = True
                        break
                if stop:
                    break
            if stop:
                break

        flush(session, ps_med, ps_zona, rows_med, rows_zona)

        dt = time.time() - t0
        rate = total / dt if dt else 0
        logger.success(f"Lecturas insertadas: {total:,} en {dt:.1f}s ({rate:,.0f} lecturas/s)")
        if CFG.preset == "demo":
            logger.success("Carga rápida lista para dashboard, API, consultas y mapa.")
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
