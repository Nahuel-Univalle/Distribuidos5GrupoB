"""SEMAPA Seeder.

Pobla catálogos, usuarios del sistema, personas, infraestructuras y medidores.

Objetivo:
- 80.000 personas naturales
- 5.000 personas jurídicas
- 100.000 infraestructuras
- 120.000 medidores IoT
- 32 radiobases LoRaWAN
"""

from __future__ import annotations

import math
import os
import random
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import bcrypt
from faker import Faker
from loguru import logger
from tqdm import tqdm

from cassandra_io import bulk_insert, connect
from csv_writer import write_csv
from excel_loader import (
    SUB_ALCALDIAS,
    load_distritos_zonas,
    load_errores,
    load_modelos,
    load_tarifas,
    load_tipos_infra,
    load_unidades_educativas,
    load_workbook,
)


EXCEL_PATH = os.getenv("SEEDER_EXCEL", "/recursos/recursos.xlsx")
SEEDS_DIR = Path(os.getenv("SEEDS_DIR", "/data/seeds"))

CONCURRENCY = int(os.getenv("SEED_CONCURRENCY", "60"))
BATCH_SIZE = int(os.getenv("SEED_BATCH_SIZE", "1000"))
SEED = int(os.getenv("SEED_RNG", "20250512"))

TARGET_INFRAESTRUCTURAS = int(os.getenv("SEED_TARGET_INFRA", "100000"))
TARGET_MEDIDORES = int(os.getenv("SEED_TARGET_MEDIDORES", "120000"))

RESET_BEFORE_SEED = os.getenv("SEED_RESET", "false").lower() in {"1", "true", "yes", "si"}

random.seed(SEED)
fake = Faker("es_ES")
Faker.seed(SEED)

CATEGORIAS = ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]


def _bs(text: str) -> bytes:
    return bcrypt.hashpw(text.encode("utf-8"), bcrypt.gensalt(rounds=12))


def jitter(lat: float, lon: float, mag: float = 0.005) -> tuple[float, float]:
    return lat + random.uniform(-mag, mag), lon + random.uniform(-mag, mag)


def gateways_32() -> list[tuple[int, str, float, float]]:
    base = [
        (1, "LoRaWan-Teleferico", -17.38922, -66.14172),
        (2, "LoRaWan-ParqueVial", -17.38100, -66.15336),
        (3, "LoRaWan-ParqueLincon", -17.36986, -66.17639),
        (4, "LoRaWan-Petrolera", -17.44408, -66.14069),
        (5, "LoRaWan-SurEste", -17.42000, -66.11000),
    ]

    centro_lat = -17.3935
    centro_lon = -66.1570
    extras = []

    for gateway_id in range(6, 33):
        idx = gateway_id - 6
        angle = (2 * math.pi * idx) / 27
        radius_lat = 0.020 + (idx % 4) * 0.006
        radius_lon = 0.025 + (idx % 5) * 0.006
        lat = centro_lat + math.sin(angle) * radius_lat
        lon = centro_lon + math.cos(angle) * radius_lon
        extras.append(
            (
                gateway_id,
                f"LoRaWan-RadioBase-{gateway_id:02d}",
                round(lat, 6),
                round(lon, 6),
            )
        )

    return base + extras


def gateway_para_zona(zona) -> int:
    return ((zona.distrito_id * 7 + zona.zona_id * 3) % 32) + 1


def gen_mac(seq: int) -> str:
    return (
        f"30:E2:"
        f"{(seq >> 24) & 0xFF:02X}:"
        f"{(seq >> 16) & 0xFF:02X}:"
        f"{(seq >> 8) & 0xFF:02X}:"
        f"{seq & 0xFF:02X}"
    )


def gen_serie(seq: int) -> str:
    return f"SN={seq // 100000:03d}-{seq % 100000:05d}-{random.randint(1000, 9999)}"


def reset_tables(session) -> None:
    tables = [
        "lecturas_raw",
        "lecturas_por_medidor",
        "lecturas_por_zona_dia",
        "lecturas_manuales",
        "cobertura_gateway",
        "facturas",
        "facturas_por_periodo",
        "medidores",
        "infraestructuras",
        "personas",
        "usuarios_sistema",
        "zonas",
        "distritos",
        "sub_alcaldias",
        "gateways",
        "modelos_medidor",
        "tarifas",
        "errores_iot",
        "tipos_infraestructura",
    ]

    logger.warning("SEED_RESET activo: limpiando tablas antes de poblar...")
    for table in tables:
        try:
            session.execute(f"TRUNCATE {table}")
            logger.info(f"Tabla limpia: {table}")
        except Exception as exc:
            logger.warning(f"No se pudo limpiar {table}: {exc}")


def seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos):
    logger.info("Insertando catálogos...")

    ps = session.prepare("INSERT INTO sub_alcaldias (sub_alcaldia_id, nombre) VALUES (?, ?)")
    bulk_insert(session, ps, SUB_ALCALDIAS, concurrency=10)

    ps = session.prepare(
        "INSERT INTO distritos (distrito_id, sub_alcaldia_id, nombre, habitantes) "
        "VALUES (?, ?, ?, ?)"
    )
    bulk_insert(
        session,
        ps,
        [(d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos],
        concurrency=20,
    )

    ps = session.prepare(
        "INSERT INTO zonas (distrito_id, zona_id, nombre, gateway_id) "
        "VALUES (?, ?, ?, ?)"
    )
    bulk_insert(
        session,
        ps,
        [(z.distrito_id, z.zona_id, z.nombre, gateway_para_zona(z)) for z in zonas],
        concurrency=40,
    )

    ps = session.prepare(
        "INSERT INTO gateways (gateway_id, nombre, latitud, longitud) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(session, ps, gateways_32(), concurrency=10)

    ps = session.prepare(
        "INSERT INTO modelos_medidor (modelo_id, marca, modelo, conectividad, aplicacion) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    bulk_insert(
        session,
        ps,
        [(m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos],
        concurrency=10,
    )

    ps = session.prepare(
        "INSERT INTO tarifas (categoria, alias, fijo_m3, usd_mes, r_13_25, r_26_50, "
        "r_51_75, r_76_100, r_101_150, r_mas_151, descripcion) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    bulk_insert(
        session,
        ps,
        [
            (
                t.categoria,
                t.alias,
                t.fijo_m3,
                t.usd_mes,
                t.r_13_25,
                t.r_26_50,
                t.r_51_75,
                t.r_76_100,
                t.r_101_150,
                t.r_mas_151,
                t.descripcion,
            )
            for t in tarifas
        ],
        concurrency=10,
    )

    ps = session.prepare("INSERT INTO errores_iot (codigo, descripcion) VALUES (?, ?)")
    bulk_insert(session, ps, errores, concurrency=10)

    ps = session.prepare(
        "INSERT INTO tipos_infraestructura (tipo_id, descripcion) VALUES (?, ?)"
    )
    bulk_insert(session, ps, [(t.tipo_id, t.descripcion) for t in tipos], concurrency=10)

    logger.success("Catálogos insertados.")


def seed_usuarios(session):
    logger.info("Insertando usuarios del sistema...")

    ps = session.prepare(
        "INSERT INTO usuarios_sistema (username, password_hash, rol, nombre, email, activo, "
        "fecha_creacion, ultimo_acceso) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )

    now = datetime.utcnow()
    usuarios = [
        (
            "alcaldia",
            _bs("Alcaldia2025!").decode(),
            "ALCALDIA",
            "Alcaldía Cochabamba",
            "alcaldia@semapa.bo",
            True,
            now,
            None,
        ),
        (
            "gerencia",
            _bs("Gerencia2025!").decode(),
            "GERENCIA",
            "Gerencia Operativa",
            "gerencia@semapa.bo",
            True,
            now,
            None,
        ),
        (
            "contabilidad",
            _bs("Contab2025!").decode(),
            "CONTABILIDAD",
            "Contabilidad",
            "contabilidad@semapa.bo",
            True,
            now,
            None,
        ),
    ]

    bulk_insert(session, ps, usuarios, concurrency=3)
    logger.success("Usuarios listos: alcaldia / gerencia / contabilidad")


def seed_personas(session, n_naturales: int = 80_000, n_juridicas: int = 5_000) -> list[uuid.UUID]:
    logger.info(f"Generando {n_naturales} personas naturales + {n_juridicas} jurídicas...")

    ps = session.prepare(
        "INSERT INTO personas (persona_id, tipo, documento, nombre, apellidos, razon_social, "
        "email, telefono, fecha_registro) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    ids: list[uuid.UUID] = []
    rows: list[tuple] = []

    now = datetime.utcnow()
    fecha_min = datetime(2018, 1, 1)
    rango_dias = (now - fecha_min).days

    pbar = tqdm(total=n_naturales + n_juridicas, desc="personas")

    for _ in range(n_naturales):
        pid = uuid.uuid4()
        ids.append(pid)

        rows.append(
            (
                pid,
                "NATURAL",
                str(random.randint(1_000_000, 12_999_999)),
                fake.first_name(),
                f"{fake.last_name()} {fake.last_name()}",
                None,
                fake.email(),
                f"7{random.randint(1000000, 9999999)}",
                fecha_min + timedelta(days=random.randint(0, rango_dias)),
            )
        )

        if len(rows) >= BATCH_SIZE:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows))
            rows.clear()

    for _ in range(n_juridicas):
        pid = uuid.uuid4()
        ids.append(pid)

        rows.append(
            (
                pid,
                "JURIDICA",
                str(random.randint(100_000_000, 999_999_999)),
                None,
                None,
                fake.company(),
                f"contacto@{fake.domain_name()}",
                f"4{random.randint(1000000, 9999999)}",
                fecha_min + timedelta(days=random.randint(0, rango_dias)),
            )
        )

        if len(rows) >= BATCH_SIZE:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows))
            rows.clear()

    if rows:
        bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
        pbar.update(len(rows))

    pbar.close()
    logger.success(f"Personas: {len(ids)} insertadas")
    return ids


def construir_plan_infraestructuras(zonas) -> list[dict]:
    raw_plan = []

    for zona in zonas:
        for categoria in CATEGORIAS:
            cantidad = int(zona.counts.get(categoria, 0) or 0)
            if cantidad > 0:
                raw_plan.append(
                    {
                        "zona": zona,
                        "categoria": categoria,
                        "source": cantidad,
                    }
                )

    total_source = sum(item["source"] for item in raw_plan)

    if total_source <= 0:
        raise RuntimeError("No existen conteos por zona/categoría para generar infraestructuras.")

    exactos = []
    total_base = 0

    for item in raw_plan:
        exact = item["source"] * TARGET_INFRAESTRUCTURAS / total_source
        base = int(math.floor(exact))
        if item["source"] > 0 and base == 0:
            base = 1
        item["cantidad"] = base
        item["residuo"] = exact - base
        exactos.append(item)
        total_base += base

    diferencia = TARGET_INFRAESTRUCTURAS - total_base

    if diferencia > 0:
        exactos.sort(key=lambda x: x["residuo"], reverse=True)
        for i in range(diferencia):
            exactos[i % len(exactos)]["cantidad"] += 1
    elif diferencia < 0:
        exactos.sort(key=lambda x: x["residuo"])
        faltante = abs(diferencia)
        i = 0
        while faltante > 0 and i < len(exactos):
            if exactos[i]["cantidad"] > 1:
                exactos[i]["cantidad"] -= 1
                faltante -= 1
            else:
                i += 1

    return exactos


def construir_medidores_por_infra(total_infra: int) -> list[int]:
    if TARGET_MEDIDORES < total_infra:
        raise RuntimeError("TARGET_MEDIDORES no puede ser menor a TARGET_INFRAESTRUCTURAS.")

    medidores_por_infra = [1] * total_infra
    extra = TARGET_MEDIDORES - total_infra

    while extra > 0:
        idx = random.randrange(total_infra)
        if medidores_por_infra[idx] < 5:
            medidores_por_infra[idx] += 1
            extra -= 1

    return medidores_por_infra


def seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades_educativas):
    logger.info("Generando infraestructuras + medidores...")

    ps_infra = session.prepare(
        "INSERT INTO infraestructuras (infraestructura_id, persona_id, tipo_infra, "
        "distrito_id, zona_id, direccion, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )

    ps_med = session.prepare(
        "INSERT INTO medidores (medidor_id, mac, numero_serie, numero_contrato, "
        "infraestructura_id, modelo_id, categoria_tarifa, gateway_id, distrito_id, zona_id, "
        "latitud, longitud, fecha_instalacion, estado) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    plan = construir_plan_infraestructuras(zonas)
    total_plan_infra = sum(item["cantidad"] for item in plan)

    if total_plan_infra != TARGET_INFRAESTRUCTURAS:
        raise RuntimeError(
            f"Plan inválido: {total_plan_infra} infraestructuras, "
            f"esperado {TARGET_INFRAESTRUCTURAS}."
        )

    medidores_por_infra = construir_medidores_por_infra(TARGET_INFRAESTRUCTURAS)

    random.shuffle(personas_ids)
    persona_idx = 0
    persona_cupo = random.randint(1, 5)

    def siguiente_persona() -> uuid.UUID:
        nonlocal persona_idx, persona_cupo

        if persona_idx >= len(personas_ids):
            random.shuffle(personas_ids)
            persona_idx = 0

        persona_id = personas_ids[persona_idx]
        persona_cupo -= 1

        if persona_cupo <= 0:
            persona_idx += 1
            persona_cupo = random.randint(1, 5)

        return persona_id

    modelos_disponibles = [1, 2, 3, 4, 5]
    pesos_modelos = [0.30, 0.20, 0.20, 0.15, 0.15]

    contrato_seq = 100_000_000
    mac_seq = 1

    fecha_min = date(2020, 1, 1)
    fecha_max = date(2025, 3, 1)
    delta_dias = (fecha_max - fecha_min).days

    educ_pendientes = list(unidades_educativas)

    infra_rows: list[tuple] = []
    med_rows: list[tuple] = []

    total_infra = 0
    total_med = 0

    pbar_infra = tqdm(total=TARGET_INFRAESTRUCTURAS, desc="infraestructuras")
    pbar_med = tqdm(total=TARGET_MEDIDORES, desc="medidores")

    for item in plan:
        zona = item["zona"]
        categoria = item["categoria"]
        cantidad = item["cantidad"]
        gateway_id = gateway_para_zona(zona)

        for _ in range(cantidad):
            infra_id = uuid.uuid4()
            persona_id = siguiente_persona()

            tipo_infra = 0
            if categoria == "P" and educ_pendientes:
                tipo_infra = 1
                educ_pendientes.pop()
            elif categoria in {"C", "CE"}:
                tipo_infra = random.choice([3, 4, 5, 9, 10])
            elif categoria == "I":
                tipo_infra = 8
            elif categoria == "S":
                tipo_infra = random.choice([6, 7])

            lat, lon = jitter(zona.centro_lat, zona.centro_lon, 0.008)

            infra_rows.append(
                (
                    infra_id,
                    persona_id,
                    tipo_infra,
                    zona.distrito_id,
                    zona.zona_id,
                    fake.street_address()[:80],
                    lat,
                    lon,
                )
            )

            cantidad_medidores = medidores_por_infra[total_infra]

            for _ in range(cantidad_medidores):
                med_id = uuid.uuid4()
                modelo_id = random.choices(modelos_disponibles, pesos_modelos)[0]

                estado_r = random.random()
                if estado_r < 0.95:
                    estado = "ACTIVO"
                elif estado_r < 0.98:
                    estado = "INACTIVO"
                else:
                    estado = "FUERA_SERVICIO"

                mlat, mlon = jitter(lat, lon, 0.0008)
                fecha_instalacion = fecha_min + timedelta(days=random.randint(0, delta_dias))

                contrato_seq += 1

                med_rows.append(
                    (
                        med_id,
                        gen_mac(mac_seq),
                        gen_serie(mac_seq),
                        contrato_seq,
                        infra_id,
                        modelo_id,
                        categoria,
                        gateway_id,
                        zona.distrito_id,
                        zona.zona_id,
                        mlat,
                        mlon,
                        fecha_instalacion,
                        estado,
                    )
                )

                mac_seq += 1
                total_med += 1
                pbar_med.update(1)

                if len(med_rows) >= BATCH_SIZE:
                    bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)
                    med_rows.clear()

            total_infra += 1
            pbar_infra.update(1)

            if len(infra_rows) >= BATCH_SIZE:
                bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY)
                infra_rows.clear()

    if infra_rows:
        bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY)

    if med_rows:
        bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)

    pbar_infra.close()
    pbar_med.close()

    logger.success(f"Infraestructuras: {total_infra} | Medidores: {total_med}")


def export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos):
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(
        SEEDS_DIR / "sub_alcaldias.csv",
        ["sub_alcaldia_id", "nombre"],
        SUB_ALCALDIAS,
    )

    write_csv(
        SEEDS_DIR / "distritos.csv",
        ["distrito_id", "sub_alcaldia_id", "nombre", "habitantes"],
        [(d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos],
    )

    write_csv(
        SEEDS_DIR / "zonas.csv",
        ["distrito_id", "zona_id", "nombre", "gateway_id", "habitantes", "total_medidores"],
        [
            (
                z.distrito_id,
                z.zona_id,
                z.nombre,
                gateway_para_zona(z),
                z.habitantes,
                z.total_medidores,
            )
            for z in zonas
        ],
    )

    write_csv(
        SEEDS_DIR / "gateways.csv",
        ["gateway_id", "nombre", "latitud", "longitud"],
        gateways_32(),
    )

    write_csv(
        SEEDS_DIR / "modelos.csv",
        ["modelo_id", "marca", "modelo", "conectividad", "aplicacion"],
        [(m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos],
    )

    write_csv(
        SEEDS_DIR / "tarifas.csv",
        [
            "categoria",
            "alias",
            "fijo_m3",
            "usd_mes",
            "r_13_25",
            "r_26_50",
            "r_51_75",
            "r_76_100",
            "r_101_150",
            "r_mas_151",
            "descripcion",
        ],
        [
            (
                t.categoria,
                t.alias,
                str(t.fijo_m3),
                str(t.usd_mes),
                str(t.r_13_25),
                str(t.r_26_50),
                str(t.r_51_75),
                str(t.r_76_100),
                str(t.r_101_150),
                str(t.r_mas_151),
                t.descripcion,
            )
            for t in tarifas
        ],
    )

    write_csv(SEEDS_DIR / "errores.csv", ["codigo", "descripcion"], errores)

    write_csv(
        SEEDS_DIR / "tipos_infra.csv",
        ["tipo_id", "descripcion"],
        [(t.tipo_id, t.descripcion) for t in tipos],
    )


def main():
    t0 = time.time()

    logger.info("=" * 60)
    logger.info("SEMAPA Seeder")
    logger.info("=" * 60)

    wb = load_workbook(EXCEL_PATH)
    distritos, zonas = load_distritos_zonas(wb)
    tarifas = load_tarifas(wb)
    modelos = load_modelos(wb)
    errores = load_errores(wb)
    tipos = load_tipos_infra(wb)
    unidades = load_unidades_educativas(wb)

    export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos)

    cluster, session = connect()

    try:
        if RESET_BEFORE_SEED:
            reset_tables(session)

        seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos)
        seed_usuarios(session)
        personas_ids = seed_personas(session)
        seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades)
    finally:
        cluster.shutdown()

    logger.success(f"Seed completado en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()