"""SEMAPA Seeder — Fase 2.

Pobla catálogos + personas + infraestructuras + medidores + usuarios sistema.

Pasos:
1. Carga Excel (Recursos_Practica_5.xlsx).
2. Escribe CSVs limpios en /data/seeds/.
3. Inserta catálogos en Cassandra.
4. Genera 85 000 personas (80 k naturales + 5 k jurídicas).
5. Distribuye 100 000+ infraestructuras según conteos por zona del Excel.
6. Genera 120 000 medidores con coordenadas controladas por distrito/zona.
7. Inserta 3 usuarios del sistema (alcaldía/gerencia/contabilidad) con bcrypt.

Optimización:
- Prepared statements.
- execute_concurrent_with_args(concurrency=100..200).
- tqdm para progreso.
"""
from __future__ import annotations

import os
import random
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
)
from external_sources import (
    ExternalSources,
    categoria_tarifa,
    load_external_sources,
    normalize_mac,
    stable_int,
)


EXCEL_PATH = os.getenv("SEEDER_EXCEL", "/recursos/recursos.xlsx")
SEEDS_DIR = Path(os.getenv("SEEDS_DIR", "/data/seeds"))
CONCURRENCY = int(os.getenv("SEED_CONCURRENCY", "120"))
SEED = int(os.getenv("SEED_RNG", "20250512"))

random.seed(SEED)
fake = Faker("es_ES")
Faker.seed(SEED)


CATEGORIAS = ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]
TARGET_INFRAESTRUCTURAS = int(os.getenv("SEED_TARGET_INFRA", "80000"))
TARGET_MEDIDORES = int(os.getenv("SEED_TARGET_MEDIDORES", "120000"))
TARGET_CONTRATOS = int(os.getenv("SEED_TARGET_CONTRATOS", "100000"))
USE_EXTERNAL_CSV = os.getenv("SEED_USE_EXTERNAL_CSV", "auto").strip().lower()  # auto|si|no


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



def _split_nombre(full_name: str) -> tuple[str, str]:
    parts = (full_name or "").strip().split()
    if not parts:
        return "SIN", "NOMBRE"
    if len(parts) == 1:
        return parts[0][:60], ""
    return parts[0][:60], " ".join(parts[1:])[:90]


def _doc_key(documento: str) -> str:
    return (documento or "").strip().upper()


def _zona_id_por_nombre(zonas, distrito_id: int, zona_nombre: str, seed: str) -> int:
    """Busca zona por nombre dentro del distrito; si el CSV trae nombre inconsistente, usa fallback estable."""
    zname = (zona_nombre or "").strip().upper()
    candidatas = [z for z in zonas if int(z.distrito_id) == int(distrito_id)]
    for z in candidatas:
        if z.nombre.strip().upper() == zname:
            return int(z.zona_id)
    # Coincidencia parcial para tildes/variantes simples.
    for z in candidatas:
        if zname and (zname in z.nombre.strip().upper() or z.nombre.strip().upper() in zname):
            return int(z.zona_id)
    if candidatas:
        return int(candidatas[stable_int(seed, len(candidatas))].zona_id)
    return 1


def seed_personas_external(session, fuentes: ExternalSources) -> dict[str, uuid.UUID]:
    """Inserta 80k naturales + 5k jurídicas, usando titulares/propietarios del CSV."""
    logger.info("Generando personas desde CSV externos: 80.000 naturales + 5.000 jurídicas...")
    ps = session.prepare(
        "INSERT INTO personas (persona_id, tipo, documento, nombre, apellidos, razon_social, "
        "email, telefono, fecha_registro) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    # Prioridad: propietarios de infraestructuras y titulares de contratos.
    titulares: dict[str, str] = {}
    for infra in fuentes.infraestructuras:
        if infra.ci:
            titulares.setdefault(_doc_key(infra.ci), infra.propietario)
    for c in fuentes.contratos:
        if c.ci_titular:
            titulares.setdefault(_doc_key(c.ci_titular), c.titular)

    items = list(titulares.items())[:80_000]
    doc_to_persona: dict[str, uuid.UUID] = {}
    rows: list[tuple] = []
    fecha_min = datetime(2018, 1, 1)
    rango_dias = (datetime.utcnow() - fecha_min).days

    pbar = tqdm(total=85_000, desc="personas csv")
    for doc, fullname in items:
        pid = uuid.uuid4()
        nombre, apellidos = _split_nombre(fullname)
        doc_to_persona[doc] = pid
        rows.append((
            pid, "NATURAL", doc[:30], nombre, apellidos, None,
            f"{doc.replace(' ', '').lower()}@correo.demo", f"7{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows)); rows.clear()

    # Si el CSV trae menos de 80k documentos, completar sintéticamente.
    while len(doc_to_persona) < 80_000:
        pid = uuid.uuid4()
        doc = f"AUTO-{len(doc_to_persona)+1:08d}"
        doc_to_persona[doc] = pid
        rows.append((
            pid, "NATURAL", doc, fake.first_name(), fake.last_name() + " " + fake.last_name(), None,
            fake.email(), f"7{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows)); rows.clear()

    for i in range(5_000):
        pid = uuid.uuid4()
        nit = f"NIT-{100000000+i}"
        doc_to_persona[nit] = pid
        rows.append((
            pid, "JURIDICA", nit, None, None, fake.company(),
            f"contacto{i}@empresa.demo", f"4{random.randint(1000000, 9999999)}",
            fecha_min + timedelta(days=random.randint(0, rango_dias)),
        ))
        if len(rows) >= 5000:
            bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
            pbar.update(len(rows)); rows.clear()
    if rows:
        bulk_insert(session, ps, rows, concurrency=CONCURRENCY)
        pbar.update(len(rows)); rows.clear()
    pbar.close()
    logger.success(f"Personas insertadas: {len(doc_to_persona):,}")
    return doc_to_persona


def seed_external_csvs(session, zonas, fuentes: ExternalSources) -> None:
    """Pobla 80k infraestructuras, 100k contratos y 120k medidores desde los CSV nuevos."""
    logger.info("Usando CSV externos del Excel actualizado para infraestructuras/contratos/medidores...")
    if len(fuentes.infraestructuras) < TARGET_INFRAESTRUCTURAS:
        raise RuntimeError(f"CSV de infraestructuras trae {len(fuentes.infraestructuras)}; se requieren {TARGET_INFRAESTRUCTURAS}")
    if len(fuentes.contratos) < TARGET_CONTRATOS:
        raise RuntimeError(f"CSV de contratos trae {len(fuentes.contratos)}; se requieren {TARGET_CONTRATOS}")
    if len(fuentes.medidores) < TARGET_MEDIDORES:
        raise RuntimeError(f"CSV de medidores trae {len(fuentes.medidores)}; se requieren {TARGET_MEDIDORES}")

    doc_to_persona = seed_personas_external(session, fuentes)
    personas_fallback = list(doc_to_persona.values())

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
    ps_contrato = session.prepare(
        "INSERT INTO contratos (numero_contrato, numero_contrato_txt, numero_catastro, persona_id, "
        "infraestructura_id, medidor_id, categoria_tarifa, categoria, fecha_contrato, estado_contrato, "
        "diametro_conexion, tipo_servicio, distrito_id, zona_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    ps_contrato_estado = session.prepare(
        "INSERT INTO contratos_por_estado (estado_contrato, distrito_id, numero_contrato, categoria_tarifa) "
        "VALUES (?, ?, ?, ?)"
    )

    infra_by_catastro: dict[str, dict] = {}
    infra_rows: list[tuple] = []
    for infra in tqdm(fuentes.infraestructuras[:TARGET_INFRAESTRUCTURAS], desc="infra csv"):
        iid = uuid.uuid4()
        doc = _doc_key(infra.ci)
        persona_id = doc_to_persona.get(doc) or personas_fallback[stable_int(infra.numero_catastro, len(personas_fallback))]
        zona_id = _zona_id_por_nombre(zonas, infra.distrito_id, infra.zona_nombre, infra.numero_catastro)
        center = zone_center(infra.distrito_id, zona_id)
        lat, lon = deterministic_point_near(center, f"infra:{infra.numero_catastro}", DEFAULT_INFRA_RADIUS_DEG)
        infra_rows.append((iid, persona_id, infra.tipo_infra, infra.distrito_id, zona_id, infra.direccion[:80], lat, lon))
        infra_by_catastro[infra.numero_catastro] = {
            "infraestructura_id": iid,
            "persona_id": persona_id,
            "distrito_id": infra.distrito_id,
            "zona_id": zona_id,
            "lat": lat,
            "lon": lon,
        }
        if len(infra_rows) >= 5000:
            bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY); infra_rows.clear()
    if infra_rows:
        bulk_insert(session, ps_infra, infra_rows, concurrency=CONCURRENCY)

    med_by_mac = {m.mac: m for m in fuentes.medidores[:TARGET_MEDIDORES]}
    medidores_usados: set[str] = set()
    med_rows: list[tuple] = []
    contrato_rows: list[tuple] = []
    contrato_estado_rows: list[tuple] = []
    med_uuid_by_mac: dict[str, uuid.UUID] = {}

    for contrato in tqdm(fuentes.contratos[:TARGET_CONTRATOS], desc="contratos+medidores"):
        infra_ref = infra_by_catastro.get(contrato.numero_catastro)
        if infra_ref is None:
            # No debería pasar con los CSV actuales, pero evitamos romper.
            infra_ref = random.choice(list(infra_by_catastro.values()))
        med_src = med_by_mac.get(contrato.medidor_iot)
        if med_src is None:
            continue
        medidores_usados.add(med_src.mac)
        mid = uuid.uuid4()
        med_uuid_by_mac[med_src.mac] = mid
        cat = contrato.subcategoria
        estado = med_src.estado if contrato.estado_contrato == "ACTIVO" else "INACTIVO"
        motivo = med_src.motivo_estado if estado != "INACTIVO" else contrato.estado_contrato
        es_actual = estado == "ACTIVO"
        lat, lon = deterministic_point_near((infra_ref["lat"], infra_ref["lon"]), f"med:{med_src.mac}", DEFAULT_MEDIDOR_RADIUS_DEG)
        gateway_id = gateway_pool_for(((infra_ref["distrito_id"] * 37 + infra_ref["zona_id"] * 11) % 14) + 1)[0]
        serie = f"SN={stable_int(med_src.mac, 900, 100)}-{stable_int(med_src.mac+':a', 90000, 10000)}-{stable_int(med_src.mac+':b', 9000, 1000)}"
        fecha_retiro = med_src.fecha_desinstalacion if not es_actual else None
        med_rows.append((
            mid, med_src.mac, serie, contrato.numero_contrato,
            infra_ref["infraestructura_id"], infra_ref["persona_id"], med_src.modelo_id, cat, gateway_id,
            infra_ref["distrito_id"], infra_ref["zona_id"], lat, lon,
            med_src.fecha_instalacion, fecha_retiro, estado, motivo, None, es_actual,
        ))
        contrato_rows.append((
            contrato.numero_contrato, contrato.numero_contrato_txt, contrato.numero_catastro,
            infra_ref["persona_id"], infra_ref["infraestructura_id"], mid, cat, contrato.categoria,
            contrato.fecha_contrato, contrato.estado_contrato, contrato.diametro_conexion,
            contrato.tipo_servicio, infra_ref["distrito_id"], infra_ref["zona_id"],
        ))
        contrato_estado_rows.append((contrato.estado_contrato, infra_ref["distrito_id"], contrato.numero_contrato, cat))
        if len(med_rows) >= 5000:
            bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY); med_rows.clear()
            bulk_insert(session, ps_contrato, contrato_rows, concurrency=CONCURRENCY); contrato_rows.clear()
            bulk_insert(session, ps_contrato_estado, contrato_estado_rows, concurrency=CONCURRENCY); contrato_estado_rows.clear()
    if med_rows:
        bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)
    if contrato_rows:
        bulk_insert(session, ps_contrato, contrato_rows, concurrency=CONCURRENCY)
    if contrato_estado_rows:
        bulk_insert(session, ps_contrato_estado, contrato_estado_rows, concurrency=CONCURRENCY)

    # 20k medidores restantes: históricos, mantenimiento, reacondicionados o sin contrato activo.
    extras = [m for m in fuentes.medidores[:TARGET_MEDIDORES] if m.mac not in medidores_usados]
    base_infras = list(infra_by_catastro.values())
    med_rows = []
    for med_src in tqdm(extras, desc="medidores sin contrato activo"):
        infra_ref = random.choice(base_infras)
        mid = uuid.uuid4()
        cat = random.choice(CATEGORIAS)
        lat, lon = deterministic_point_near((infra_ref["lat"], infra_ref["lon"]), f"med-extra:{med_src.mac}", DEFAULT_MEDIDOR_RADIUS_DEG)
        gateway_id = gateway_pool_for(((infra_ref["distrito_id"] * 37 + infra_ref["zona_id"] * 11) % 14) + 1)[0]
        serie = f"SN={stable_int(med_src.mac, 900, 100)}-{stable_int(med_src.mac+':a', 90000, 10000)}-{stable_int(med_src.mac+':b', 9000, 1000)}"
        extra_estado = med_src.estado if med_src.estado != "ACTIVO" else "REEMPLAZADO"
        extra_motivo = med_src.motivo_estado if med_src.estado != "ACTIVO" else "SIN_CONTRATO_ACTIVO"
        med_rows.append((
            mid, med_src.mac, serie, 0,
            infra_ref["infraestructura_id"], infra_ref["persona_id"], med_src.modelo_id, cat, gateway_id,
            infra_ref["distrito_id"], infra_ref["zona_id"], lat, lon,
            med_src.fecha_instalacion, med_src.fecha_desinstalacion, extra_estado, extra_motivo,
            None, False,
        ))
        if len(med_rows) >= 5000:
            bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY); med_rows.clear()
    if med_rows:
        bulk_insert(session, ps_med, med_rows, concurrency=CONCURRENCY)

    logger.success(
        f"CSV actualizado cargado: {TARGET_INFRAESTRUCTURAS:,} infraestructuras, "
        f"{TARGET_CONTRATOS:,} contratos y {TARGET_MEDIDORES:,} medidores IoT con 14 radiobases"
    )

def seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades_educativas):
    """Genera exactamente 100 000 infraestructuras y 120 000 medidores.

    La hoja Distritos distribuye 100 000 registros base. En esta versión esos
    registros se interpretan como infraestructuras/servicios base, no como el
    total final de medidores. Luego se añaden 20 000 medidores adicionales para
    representar reemplazos, medidores dañados, medidores viejos, retiros o
    múltiples puntos de consumo en una misma infraestructura.

    Relación defendible para exposición:
        persona -> infraestructura/servicio -> historial de medidores
    """
    logger.info("Generando infraestructuras + medidores según consigna...")
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

    mac_seq = 0x100000

    def gen_mac() -> str:
        # Formato de 5 octetos para coincidir con el ejemplo del enunciado.
        nonlocal mac_seq
        mac_seq += 1
        return "AB:CB:%02X:%02X:%02X" % ((mac_seq >> 16) & 0xFF, (mac_seq >> 8) & 0xFF, mac_seq & 0xFF)

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
                estado = "ACTIVO" if estado_r < 0.955 else ("INACTIVO" if estado_r < 0.982 else "FUERA_SERVICIO")
                motivo = "INSTALACION_IOT" if estado == "ACTIVO" else ("BAJA_ADMINISTRATIVA" if estado == "INACTIVO" else "SIN_REPORTE")
                mlat, mlon = deterministic_point_near((lat, lon), str(med_id), DEFAULT_MEDIDOR_RADIUS_DEG)
                fecha_inst = fecha_min + timedelta(days=random.randint(0, delta_dias))

                infra_rows.append((
                    infra_id, persona_id, tipo_infra,
                    zona.distrito_id, zona.zona_id,
                    fake.street_address()[:80], lat, lon,
                ))
                med_rows.append((
                    med_id, gen_mac(), gen_serie(), contrato_actual,
                    infra_id, persona_id, modelo_id, cat, gateway_id,
                    zona.distrito_id, zona.zona_id, mlat, mlon,
                    fecha_inst, None, estado, motivo, None, estado == "ACTIVO",
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

    export_csvs(wb, distritos, zonas, tarifas, modelos, errores, tipos)

    cluster, session = connect()
    try:
        seed_catalogos(session, zonas, distritos, tarifas, modelos, errores, tipos)
        seed_usuarios(session)

        fuentes = load_external_sources(load_lecturas_csv=False)
        usar_csv = (USE_EXTERNAL_CSV == "si") or (USE_EXTERNAL_CSV == "auto" and fuentes.complete_for_base_seed)
        if usar_csv:
            logger.info("SEED_USE_EXTERNAL_CSV activo: se poblará con CSV del Excel actualizado.")
            seed_external_csvs(session, zonas, fuentes)
        else:
            logger.warning("No se encontraron CSV externos completos; se usará seeder sintético anterior.")
            personas_ids = seed_personas(session)
            seed_infraestructuras_y_medidores(session, zonas, personas_ids, unidades)
    finally:
        cluster.shutdown()

    logger.success(f"Seed completado en {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
