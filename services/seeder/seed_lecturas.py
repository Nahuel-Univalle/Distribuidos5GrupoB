"""SEMAPA — Seeder de lecturas IoT.

Versión v18 alineada al PDF actualizado y a los CSV del Excel:
- 120.000 medidores IoT.
- 14 radiobases LoRaWAN.
- lecturas de febrero, marzo y abril desde `data/external/lecturas_iot.csv`
  (aprox. 100.000 lecturas por mes; no siempre llegan todas).
- 0,5% de errores / lecturas inconsistentes y registros faltantes según origen.

Modo recomendado:
    docker compose run --rm seeder python seed_lecturas.py

Si no existen los CSV, se usa un fallback sintético con presets:
    LECTURAS_PRESET=demo | exposicion | full | custom
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
from external_sources import load_lecturas, normalize_mac


@dataclass(frozen=True)
class LecturasConfig:
    source: str
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
    "demo": {"limite_medidores": 5000, "por_dia": 1, "step_dias": 14, "batch": 10000, "concurrency": 300, "max_filas": 0},
    "exposicion": {"limite_medidores": 12000, "por_dia": 1, "step_dias": 14, "batch": 12000, "concurrency": 300, "max_filas": 0},
    "full": {"limite_medidores": 0, "por_dia": 3, "step_dias": 1, "batch": 10000, "concurrency": 300, "max_filas": 0},
    "custom": {},
}

RESIDENCIALES = {"R1", "R2", "R3", "R4"}
TODOS_BLOQUES = [0, 8, 16]


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def env_date(name: str, default: str) -> date:
    raw = os.getenv(name, default)
    return datetime.strptime(raw, "%Y-%m-%d").date()


def build_config() -> LecturasConfig:
    preset = os.getenv("LECTURAS_PRESET", "demo").strip().lower()
    if preset not in PRESETS:
        raise ValueError(f"LECTURAS_PRESET inválido: {preset}. Usa demo, exposicion, full o custom.")
    p = PRESETS[preset]
    return LecturasConfig(
        source=os.getenv("LECTURAS_SOURCE", "csv").strip().lower(),  # csv|synthetic
        preset=preset,
        # Fallback sintético. El CSV ya trae febrero-marzo-abril 2026.
        desde=env_date("LECTURAS_DESDE", "2026-02-01"),
        hasta=env_date("LECTURAS_HASTA", "2026-04-30"),
        concurrency=max(1, env_int("LECTURAS_CONCURRENCY", p.get("concurrency", 200))),
        batch=max(100, env_int("LECTURAS_BATCH", p.get("batch", 5000))),
        limite_medidores=max(0, env_int("LECTURAS_LIMITE_MEDIDORES", p.get("limite_medidores", 0))),
        por_dia=max(1, min(3, env_int("LECTURAS_POR_DIA", p.get("por_dia", 3)))),
        step_dias=max(1, env_int("LECTURAS_STEP_DIAS", p.get("step_dias", 1))),
        seed=env_int("SEED_RNG", 20250512),
        max_filas=max(0, env_int("LECTURAS_MAX_FILAS", p.get("max_filas", 0))),
        confirmar_full=os.getenv("LECTURAS_CONFIRMAR_FULL", "").strip().upper() == "SI",
    )


CFG = build_config()
random.seed(CFG.seed)
BLOQUES = TODOS_BLOQUES[: CFG.por_dia]


def consumo_para(cat: str, hora_int: int) -> int:
    if cat in RESIDENCIALES:
        if 0 <= hora_int < 8:
            return random.randint(0, 1300)
        if 8 <= hora_int < 16:
            return random.randint(0, 380)
        return random.randint(0, 190)
    return random.randint(0, 250)


def status_para() -> int:
    r = random.random()
    if r < 0.0001:  # 0,01% no enviado / inconsistente simulado
        return 9
    if r < 0.0051:  # 0,5% errores por solapamiento/atenuación
        return random.randint(3, 8)
    if r < 0.03:
        return 2  # lectura manual o validada
    return 1


def sample_estratificado(rows: list[tuple], limite: int) -> list[tuple]:
    if not limite or len(rows) <= limite:
        return rows
    grupos: dict[tuple, deque] = defaultdict(deque)
    for row in rows:
        _med_id, _mac, cat, _gw, dist_id, zona_id = row
        grupos[(dist_id, zona_id, cat)].append(row)
    seleccion: list[tuple] = []
    keys = list(grupos.keys())
    random.shuffle(keys)
    for k in keys:
        if len(seleccion) >= limite:
            break
        if grupos[k]:
            seleccion.append(grupos[k].popleft())
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
    """Trae (medidor_id, mac, categoria_tarifa, gateway_id, distrito_id, zona_id)."""
    logger.info("Cargando medidores actuales/operativos...")
    q = "SELECT medidor_id, mac, categoria_tarifa, gateway_id, distrito_id, zona_id, estado FROM medidores"
    rows = []
    for r in session.execute(q):
        # Para CSV de lecturas necesitamos mapear incluso algunos no-activos si vienen del archivo.
        rows.append((r.medidor_id, normalize_mac(r.mac), r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id))
    usados = sample_estratificado(rows, CFG.limite_medidores) if CFG.source != "csv" else rows
    logger.info(f"Medidores encontrados: {len(rows):,} | usados en modo {CFG.source}: {len(usados):,}")
    return usados


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
    rows_med.clear(); rows_zona.clear()


def seed_from_csv(session, ps_med, ps_zona, medidores: list[tuple]) -> int:
    """Carga lecturas_iot.csv y lo cruza contra la tabla medidores por MAC."""
    max_rows = CFG.max_filas
    lecturas = load_lecturas(max_rows=max_rows)
    if not lecturas:
        logger.warning("No se encontró data/external/lecturas_iot.csv; se usará fallback sintético.")
        return -1

    by_mac = {mac: (mid, cat, gw, dist, zona) for mid, mac, cat, gw, dist, zona in medidores}
    rows_med: list[tuple] = []
    rows_zona: list[tuple] = []
    total = 0
    omitidas = 0

    logger.info(f"Cargando lecturas CSV: {len(lecturas):,} filas útiles")
    for l in tqdm(lecturas, desc="lecturas csv"):
        meta = by_mac.get(l.mac)
        if meta is None:
            omitidas += 1
            continue
        med_id, cat, gw_default, dist_id, zona_id = meta
        gateway_id = l.radiobase or gw_default or 1
        if not 1 <= int(gateway_id) <= 14:
            gateway_id = ((int(gateway_id) - 1) % 14) + 1
        consumo = max(0, int(l.lectura_actual) - int(l.lectura_anterior))
        status = 1 if l.radiobase else 9
        # Mantener errores cerca de lo pedido aunque el CSV no traiga status explícito.
        if status == 1 and random.random() < 0.005:
            status = random.randint(3, 8)
        anio_mes = l.fecha_hora.year * 100 + l.fecha_hora.month
        rows_med.append((med_id, anio_mes, l.fecha_hora, int(gateway_id), int(l.lectura_actual), consumo, status))
        rows_zona.append((int(dist_id), int(zona_id), l.fecha_hora.date(), l.fecha_hora.hour, med_id, consumo, cat))
        total += 1
        if len(rows_med) >= CFG.batch:
            flush(session, ps_med, ps_zona, rows_med, rows_zona)
    flush(session, ps_med, ps_zona, rows_med, rows_zona)
    logger.info(f"Lecturas CSV omitidas por MAC no encontrado: {omitidas:,}")
    return total


def seed_synthetic(session, ps_med, ps_zona, medidores: list[tuple]) -> int:
    medidores = sample_estratificado(medidores, CFG.limite_medidores)
    dias = fechas()
    esperado = len(medidores) * len(dias) * CFG.por_dia
    logger.info(
        f"Fallback sintético | período {CFG.desde}..{CFG.hasta} | días={len(dias)} | "
        f"medidores={len(medidores):,} | lecturas/día={CFG.por_dia} | lecturas≈{esperado:,}"
    )
    if CFG.preset == "full" and not CFG.confirmar_full:
        logger.error("Carga full pesada. Usa LECTURAS_CONFIRMAR_FULL=SI para confirmar.")
        return 0

    acumulado: dict[uuid.UUID, int] = {m[0]: random.randint(100_000, 500_000) for m in medidores}
    rows_med: list[tuple] = []
    rows_zona: list[tuple] = []
    total = 0
    stop = False
    for d in tqdm(dias, desc="dias"):
        anio_mes = d.year * 100 + d.month
        for hora_int in BLOQUES:
            fecha_hora = datetime(d.year, d.month, d.day, hora_int, 0, 0)
            for med_id, _mac, cat, gw_id, dist_id, zona_id in medidores:
                consumo = consumo_para(cat, hora_int)
                acumulado[med_id] += consumo
                status = status_para()
                rows_med.append((med_id, anio_mes, fecha_hora, gw_id, acumulado[med_id], consumo, status))
                rows_zona.append((dist_id, zona_id, d, hora_int, med_id, consumo, cat))
                total += 1
                if CFG.max_filas and total >= CFG.max_filas:
                    stop = True; break
                if len(rows_med) >= CFG.batch:
                    flush(session, ps_med, ps_zona, rows_med, rows_zona)
            if stop: break
        if stop: break
    flush(session, ps_med, ps_zona, rows_med, rows_zona)
    return total


def main():
    t0 = time.time()
    cluster, session = connect()
    try:
        medidores = fetch_medidores(session)
        if not medidores:
            logger.error("No hay medidores. Ejecuta seed.py primero.")
            return
        ps_med = session.prepare(
            "INSERT INTO lecturas_por_medidor (medidor_id, anio_mes, fecha_hora, gateway_id, "
            "lectura_litros, consumo_litros, status) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        ps_zona = session.prepare(
            "INSERT INTO lecturas_por_zona_dia (distrito_id, zona_id, fecha, hora, medidor_id, "
            "consumo_litros, categoria_tarifa) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        total = -1
        if CFG.source == "csv":
            total = seed_from_csv(session, ps_med, ps_zona, medidores)
        if total < 0:
            total = seed_synthetic(session, ps_med, ps_zona, medidores)
        logger.success(f"Lecturas insertadas: {total:,} en {time.time() - t0:.1f}s")
    finally:
        cluster.shutdown()


if __name__ == "__main__":
    main()
