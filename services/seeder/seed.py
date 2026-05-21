"""SEMAPA Seeder — Fase 2.

Pobla catálogos + personas + infraestructuras + medidores + usuarios sistema.

Pasos:
1. Carga Excel (Recursos_Practica_5.xlsx).
2. Escribe CSVs limpios en /data/seeds/.
3. Inserta catálogos en Cassandra.
4. Genera 85 000 personas (80 k naturales + 5 k jurídicas).
5. Distribuye exactamente 100 000 infraestructuras según conteos por zona/tarifa del XLSX nuevo.
6. Genera 120 000 medidores con coordenadas controladas por distrito/zona y plantillas de Catastro/Contratos/Medidores.
7. Inserta 3 usuarios del sistema (alcaldía/gerencia/contabilidad) con bcrypt.

Optimización:
- Prepared statements.
- execute_concurrent_with_args(concurrency=100..200).
- tqdm para progreso.
"""
from __future__ import annotations

import os
import random
import re
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import bcrypt
from cassandra.query import PreparedStatement
from faker import Faker
from loguru import logger
from tqdm import tqdm

from cassandra_io import bulk_insert, connect
from csv_writer import write_csv
from geo_reference import DEFAULT_INFRA_RADIUS_DEG, DEFAULT_MEDIDOR_RADIUS_DEG, deterministic_point_near, zone_center
from excel_loader import (
    SUB_ALCALDIAS,
    gateways,
    gateway_pool_for,
    load_distritos_zonas,
    load_errores,
    load_modelos,
    load_tarifas,
    load_tipos_infra,
    load_unidades_educativas,
    load_workbook,
    load_infraestructura_templates,
    load_contratos_templates,
    load_medidores_templates,
    load_lecturas_templates,
    make_catastro_number,
)


EXCEL_PATH = os.getenv("SEEDER_EXCEL", "/recursos/recursos.xlsx")
SEEDS_DIR = Path(os.getenv("SEEDS_DIR", "/data/seeds"))
CONCURRENCY = int(os.getenv("SEED_CONCURRENCY", "120"))
SEED = int(os.getenv("SEED_RNG", "20250512"))

random.seed(SEED)
fake = Faker("es_ES")
Faker.seed(SEED)


CATEGORIAS = ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]
TARGET_INFRAESTRUCTURAS = int(os.getenv("SEED_TARGET_INFRA", "100000"))
TARGET_MEDIDORES = int(os.getenv("SEED_TARGET_MEDIDORES", "120000"))


def _bs(text: str) -> bytes:
    return bcrypt.hashpw(text.encode("utf-8"), bcrypt.gensalt(rounds=12))


def jitter(lat: float, lon: float, mag: float = 0.005) -> tuple[float, float]:
    return (lat + random.uniform(-mag, mag), lon + random.uniform(-mag, mag))


def seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos):
    logger.info("Insertando catálogos...")

    # sub_alcaldias
    ps = session.prepare("INSERT INTO sub_alcaldias (sub_alcaldia_id, nombre) VALUES (?, ?)")
    bulk_insert(session, ps, SUB_ALCALDIAS, concurrency=10)

    # distritos
    ps = session.prepare(
        "INSERT INTO distritos (distrito_id, sub_alcaldia_id, nombre, habitantes) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [(d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos],
        concurrency=20,
    )

    # zonas
    ps = session.prepare(
        "INSERT INTO zonas (distrito_id, zona_id, nombre, gateway_id) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [(z.distrito_id, z.zona_id, z.nombre, z.gateway_id) for z in zonas],
        concurrency=40,
    )

    # gateways
    ps = session.prepare(
        "INSERT INTO gateways (gateway_id, nombre, latitud, longitud) VALUES (?, ?, ?, ?)"
    )
    bulk_insert(session, ps, gateways(), concurrency=5)

    # modelos
    ps = session.prepare(
        "INSERT INTO modelos_medidor (modelo_id, marca, modelo, conectividad, aplicacion) "
        "VALUES (?, ?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [(m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos],
        concurrency=5,
    )

    # tarifas
    ps = session.prepare(
        "INSERT INTO tarifas (categoria, alias, fijo_m3, usd_mes, r_13_25, r_26_50, "
        "r_51_75, r_76_100, r_101_150, r_mas_151, descripcion) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    bulk_insert(
        session, ps,
        [
            (t.categoria, t.alias, t.fijo_m3, t.usd_mes, t.r_13_25, t.r_26_50,
             t.r_51_75, t.r_76_100, t.r_101_150, t.r_mas_151, t.descripcion)
            for t in tarifas
        ],
        concurrency=5,
    )

    # errores
    ps = session.prepare("INSERT INTO errores_iot (codigo, descripcion) VALUES (?, ?)")
    bulk_insert(session, ps, errores, concurrency=5)

    # tipos infraestructura
    ps = session.prepare("INSERT INTO tipos_infraestructura (tipo_id, descripcion) VALUES (?, ?)")
    bulk_insert(session, ps, [(t.tipo_id, t.descripcion) for t in tipos], concurrency=5)

    logger.success("Catálogos insertados.")


def seed_usuarios(session):
    logger.info("Insertando usuarios del sistema...")
    ps = session.prepare(
        "INSERT INTO usuarios_sistema (username, password_hash, rol, nombre, email, activo, "
        "fecha_creacion, ultimo_acceso) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    now = datetime.utcnow()
    creds = [
        ("alcaldia", _bs("Alcaldia2025!").decode(), "ALCALDIA", "Alcaldía Cochabamba",
         "alcaldia@semapa.bo", True, now, None),
        ("gerencia", _bs("Gerencia2025!").decode(), "GERENCIA", "Gerencia Operativa",
         "gerencia@semapa.bo", True, now, None),
        ("contabilidad", _bs("Contab2025!").decode(), "CONTABILIDAD", "Contabilidad",
         "contabilidad@semapa.bo", True, now, None),
    ]
    bulk_insert(session, ps, creds, concurrency=3)
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
        ci = str(random.randint(1_000_000, 12_999_999))
        rows.append((
            pid, "NATURAL", ci,
            fake.first_name(), fake.last_name() + " " + fake.last_name(),
            None,
            fake.email(), f"7{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows))
            rows.clear()

    for _ in range(n_juridicas):
        pid = uuid.uuid4()
        ids.append(pid)
        nit = str(random.randint(100_000_000, 999_999_999))
        rows.append((
            pid, "JURIDICA", nit,
            None, None, fake.company(),
            f"contacto@{fake.domain_name()}", f"4{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows))
            rows.clear()

    if rows:
        bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
        pbar.update(len(rows))
    pbar.close()

    logger.success(f"Personas: {len(ids)} insertadas")
    return ids


def seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades_educativas, infra_templates=None, contrato_templates=None, medidor_templates=None):
    """Genera exactamente 100 000 infraestructuras y 120 000 medidores.

    La hoja Distritos distribuye 100 000 registros base. En esta versión esos
    registros se interpretan como infraestructuras/servicios base, no como el
    total final de medidores. Luego se añaden 20 000 medidores adicionales para
    representar reemplazos, medidores dañados, medidores viejos, retiros o
    múltiples puntos de consumo en una misma infraestructura.

    Relación defendible para exposición:
        persona -> infraestructura/servicio -> historial de medidores
    """
    logger.info("Generando infraestructuras + medidores según consigna y XLSX nuevo...")
    infra_templates = list(infra_templates or [])
    contrato_templates = list(contrato_templates or [])
    medidor_templates = list(medidor_templates or [])
    ps_infra = session.prepare(
        "INSERT INTO infraestructuras (infraestructura_id, persona_id, tipo_infra, "
        "distrito_id, zona_id, direccion, latitud, longitud) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    ps_med = session.prepare(
        "INSERT INTO medidores (medidor_id, mac, numero_serie, numero_contrato, "
        "infraestructura_id, persona_id, modelo_id, categoria_tarifa, gateway_id, distrito_id, zona_id, "
        "latitud, longitud, fecha_instalacion, fecha_retiro, estado, motivo_estado, "
        "medidor_anterior_id, es_medidor_actual) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    # Construimos una bolsa de propietarios para que una persona pueda tener 1..5
    # infraestructuras, como indicó el docente. No se fuerza 1 persona = 1 medidor.
    owner_pool: list[uuid.UUID] = []
    while len(owner_pool) < TARGET_INFRAESTRUCTURAS:
        shuffled = list(personas_ids)
        random.shuffle(shuffled)
        for pid in shuffled:
            owner_pool.extend([pid] * random.randint(1, 5))
            if len(owner_pool) >= TARGET_INFRAESTRUCTURAS:
                break
    random.shuffle(owner_pool)
    owner_idx = 0

    def siguiente_persona() -> uuid.UUID:
        nonlocal owner_idx
        pid = owner_pool[owner_idx]
        owner_idx += 1
        return pid

    calles_base = [
        "Av. América", "Av. Beijing", "Av. Blanco Galindo", "Av. Melchor Pérez",
        "Av. Juan de la Rosa", "Av. Heroínas", "Av. Circunvalación", "Av. Villazón",
        "Calle Baptista", "Calle Lanza", "Calle Sucre", "Calle Jordán",
    ]

    def template_infra() :
        return random.choice(infra_templates) if infra_templates else None

    def template_contrato():
        return random.choice(contrato_templates) if contrato_templates else None

    def template_medidor():
        return random.choice(medidor_templates) if medidor_templates else None

    def direccion_realista(zona_nombre: str, distrito_id: int, zona_id: int, infra_seq: int) -> str:
        tpl = template_infra()
        base_dir = tpl.direccion if tpl and tpl.direccion else f"{random.choice(calles_base)} N° {random.randint(100, 4999)}"
        manzano = tpl.manzano if tpl and tpl.manzano is not None else random.randint(1, 999)
        lote = tpl.lote if tpl and tpl.lote is not None else random.randint(1, 9999)
        catastro = make_catastro_number(distrito_id, zona_id, manzano, lote, infra_seq % 1000)
        return f"{base_dir[:55]} | Zona: {zona_nombre[:25]} | Catastro: {catastro}"[:120]

    def estado_desde_contrato(default_estado: str) -> tuple[str, str, bool]:
        tpl = template_contrato()
        estado_cto = (tpl.estado_contrato if tpl else "").upper()
        if estado_cto == "ACTIVO":
            return "ACTIVO", "CONTRATO_ACTIVO", True
        if estado_cto == "MOROSO":
            return "ACTIVO", "CONTRATO_MOROSO", True
        if estado_cto == "CORTADO":
            return "FUERA_SERVICIO", "CORTE_SERVICIO", False
        if default_estado == "ACTIVO":
            return "ACTIVO", "INSTALACION_IOT", True
        if default_estado == "INACTIVO":
            return "INACTIVO", "BAJA_ADMINISTRATIVA", False
        return "FUERA_SERVICIO", "SIN_REPORTE", False

    mac_seq = 0x100000

    def gen_mac() -> str:
        # Usa ejemplos de la hoja Medidores cuando existan; si no, genera MAC estable.
        nonlocal mac_seq
        tpl = template_medidor()
        if tpl and tpl.medidor_iot and re.match(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$", tpl.medidor_iot):
            # Se mezcla con secuencia para evitar colisiones exactas.
            mac_seq += 1
            prefix = tpl.medidor_iot.split(":")[:3]
            return ":".join(prefix + [f"{(mac_seq >> 16) & 0xFF:02X}", f"{(mac_seq >> 8) & 0xFF:02X}", f"{mac_seq & 0xFF:02X}"])
        mac_seq += 1
        return "AB:CB:%02X:%02X:%02X:%02X" % ((mac_seq >> 24) & 0xFF, (mac_seq >> 16) & 0xFF, (mac_seq >> 8) & 0xFF, mac_seq & 0xFF)

    def gen_serie() -> str:
        return f"SN={random.randint(100, 999)}-{random.randint(10000, 99999)}-{random.randint(1000, 9999)}"

    def tipo_infra_por_categoria(cat: str, educativas_restantes: list) -> int:
        if cat == "P":
            # Preferencial: colegios, hospitales, asilos, iglesias.
            if educativas_restantes:
                educativas_restantes.pop()
                return 1
            return random.choice([1, 2, 3, 4])
        if cat == "S":
            # Social: espacios y entidades públicas.
            return random.choice([5, 6, 7])
        if cat in {"C", "CE"}:
            return random.choice([6, 11, 12])
        if cat == "I":
            return random.choice([11, 12])
        # Residencial: vivienda, edificio, condominio o terreno.
        return random.choices([9, 11, 12, 10, 8], weights=[72, 12, 10, 4, 2])[0]

    modelos_disponibles = [1, 2, 3, 4, 5]
    pesos_modelos = [0.30, 0.20, 0.20, 0.15, 0.15]
    fecha_min = date(2020, 1, 1)
    fecha_max = date(2025, 3, 1)
    delta_dias = (fecha_max - fecha_min).days
    contrato_seq = 100_000_000

    infra_rows: list[tuple] = []
    med_rows: list[tuple] = []
    infra_records: list[dict] = []
    educ_pendientes = list(unidades_educativas)

    def flush(force: bool = False) -> None:
        nonlocal infra_rows, med_rows
        if force or len(infra_rows) >= 5000:
            if infra_rows:
                bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY)
                infra_rows.clear()
        if force or len(med_rows) >= 5000:
            if med_rows:
                bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)
                med_rows.clear()

    total_infra = 0
    total_med = 0

    # 1) Base: 100 000 infraestructuras, una instalación vigente por infraestructura.
    for zona in tqdm(zonas, desc="infraestructuras base"):
        for cat in CATEGORIAS:
            cantidad = zona.counts.get(cat, 0)
            if cantidad <= 0:
                continue
            for _ in range(cantidad):
                if total_infra >= TARGET_INFRAESTRUCTURAS:
                    break
                infra_id = uuid.uuid4()
                persona_id = siguiente_persona()
                tipo_infra = tipo_infra_por_categoria(cat, educ_pendientes)
                center = zone_center(zona.distrito_id, zona.zona_id)
                lat, lon = deterministic_point_near(center, str(infra_id), DEFAULT_INFRA_RADIUS_DEG)
                contrato_seq += 1
                contrato_actual = contrato_seq
                gateway_id = random.choice(gateway_pool_for(zona.gateway_id))
                med_id = uuid.uuid4()
                modelo_id = random.choices(modelos_disponibles, pesos_modelos)[0]
                estado_r = random.random()
                estado_default = "ACTIVO" if estado_r < 0.955 else ("INACTIVO" if estado_r < 0.982 else "FUERA_SERVICIO")
                estado, motivo, es_actual_base = estado_desde_contrato(estado_default)
                mlat, mlon = deterministic_point_near((lat, lon), str(med_id), DEFAULT_MEDIDOR_RADIUS_DEG)
                fecha_inst = fecha_min + timedelta(days=random.randint(0, delta_dias))

                infra_rows.append((
                    infra_id, persona_id, tipo_infra,
                    zona.distrito_id, zona.zona_id,
                    direccion_realista(zona.nombre, zona.distrito_id, zona.zona_id, total_infra), lat, lon,
                ))
                med_rows.append((
                    med_id, gen_mac(), gen_serie(), contrato_actual,
                    infra_id, persona_id, modelo_id, cat, gateway_id,
                    zona.distrito_id, zona.zona_id, mlat, mlon,
                    fecha_inst, None, estado, motivo, None, es_actual_base,
                ))
                infra_records.append({
                    "infraestructura_id": infra_id,
                    "persona_id": persona_id,
                    "distrito_id": zona.distrito_id,
                    "zona_id": zona.zona_id,
                    "lat": lat,
                    "lon": lon,
                    "cat": cat,
                    "gateway_base": zona.gateway_id,
                    "contrato": contrato_actual,
                    "medidor_actual_id": med_id,
                    "fecha_actual": fecha_inst,
                })
                total_infra += 1
                total_med += 1
                flush()
            if total_infra >= TARGET_INFRAESTRUCTURAS:
                break
        if total_infra >= TARGET_INFRAESTRUCTURAS:
            break

    # 2) Adicionales: 20 000 medidores asociados a infraestructuras ya existentes.
    # Sirven para historial y para justificar que una persona/infraestructura puede
    # tener más de un medidor por reemplazo, antigüedad, daño o multi-toma.
    motivos_hist = [
        ("REEMPLAZADO", "MEDIDOR_VIEJO"),
        ("DAÑADO", "DAÑO_CAUDALIMETRO"),
        ("RETIRADO", "CAMBIO_A_IOT"),
        ("FUERA_SERVICIO", "SIN_REPORTE"),
        ("ACTIVO", "SEGUNDA_TOMA_MISMA_INFRAESTRUCTURA"),
    ]
    pbar = tqdm(total=max(0, TARGET_MEDIDORES - total_med), desc="medidores adicionales")
    while total_med < TARGET_MEDIDORES:
        base = random.choice(infra_records)
        estado, motivo = random.choices(motivos_hist, weights=[35, 20, 20, 15, 10])[0]
        es_actual = estado == "ACTIVO"
        contrato = base["contrato"] if not es_actual else contrato_seq + 1
        if es_actual:
            contrato_seq += 1
        med_id = uuid.uuid4()
        modelo_id = random.choices(modelos_disponibles, pesos_modelos)[0]
        lat, lon = deterministic_point_near((base["lat"], base["lon"]), str(med_id), DEFAULT_MEDIDOR_RADIUS_DEG)
        fecha_inst = fecha_min + timedelta(days=random.randint(0, delta_dias))
        fecha_retiro = None
        if not es_actual:
            retiro_min = fecha_inst + timedelta(days=30)
            retiro_max = date(2025, 5, 1)
            if retiro_min < retiro_max:
                fecha_retiro = retiro_min + timedelta(days=random.randint(0, (retiro_max - retiro_min).days))
        med_rows.append((
            med_id, gen_mac(), gen_serie(), contrato,
            base["infraestructura_id"], base["persona_id"], modelo_id, base["cat"],
            random.choice(gateway_pool_for(base["gateway_base"])),
            base["distrito_id"], base["zona_id"], lat, lon,
            fecha_inst, fecha_retiro, estado, motivo, base["medidor_actual_id"], es_actual,
        ))
        total_med += 1
        pbar.update(1)
        flush()
    pbar.close()
    flush(force=True)

    logger.success(f"Infraestructuras: {total_infra} | Medidores: {total_med}")

def export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos):
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(SEEDS_DIR / "sub_alcaldias.csv", ["sub_alcaldia_id", "nombre"], SUB_ALCALDIAS)
    write_csv(
        SEEDS_DIR / "distritos.csv",
        ["distrito_id", "sub_alcaldia_id", "nombre", "habitantes"],
        [(d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos],
    )
    write_csv(
        SEEDS_DIR / "zonas.csv",
        ["distrito_id", "zona_id", "nombre", "gateway_id", "habitantes", "total_medidores"],
        [(z.distrito_id, z.zona_id, z.nombre, z.gateway_id, z.habitantes, z.total_medidores) for z in zonas],
    )
    write_csv(SEEDS_DIR / "gateways.csv", ["gateway_id", "nombre", "latitud", "longitud"], gateways())
    write_csv(
        SEEDS_DIR / "modelos.csv",
        ["modelo_id", "marca", "modelo", "conectividad", "aplicacion"],
        [(m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos],
    )
    write_csv(
        SEEDS_DIR / "tarifas.csv",
        ["categoria", "alias", "fijo_m3", "usd_mes", "r_13_25", "r_26_50", "r_51_75",
         "r_76_100", "r_101_150", "r_mas_151", "descripcion"],
        [(t.categoria, t.alias, str(t.fijo_m3), str(t.usd_mes), str(t.r_13_25),
          str(t.r_26_50), str(t.r_51_75), str(t.r_76_100), str(t.r_101_150),
          str(t.r_mas_151), t.descripcion) for t in tarifas],
    )
    write_csv(SEEDS_DIR / "errores.csv", ["codigo", "descripcion"], errores)
    write_csv(
        SEEDS_DIR / "tipos_infra.csv", ["tipo_id", "descripcion"],
        [(t.tipo_id, t.descripcion) for t in tipos],
    )


def main():
    t0 = time.time()
    logger.info("=" * 60)
    logger.info("SEMAPA Seeder — Fase 2")
    logger.info("=" * 60)

    wb = load_workbook(EXCEL_PATH)
    distritos, zonas = load_distritos_zonas(wb)
    tarifas = load_tarifas(wb)
    modelos = load_modelos(wb)
    errores = load_errores(wb)
    tipos = load_tipos_infra(wb)
    unidades = load_unidades_educativas(wb)
    infra_templates = load_infraestructura_templates(wb)
    contrato_templates = load_contratos_templates(wb)
    medidor_templates = load_medidores_templates(wb)
    _lectura_templates = load_lecturas_templates(wb)  # valida hoja nueva; seed_lecturas genera la serie masiva

    export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos)

    cluster, session = connect()
    try:
        seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos)
        seed_usuarios(session)
        personas_ids = seed_personas(session)
        seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades, infra_templates, contrato_templates, medidor_templates)
    finally:
        cluster.shutdown()

    logger.success(f"Seed completado en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
