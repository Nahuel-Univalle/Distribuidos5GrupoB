from __future__ import annotations

import csv
import hashlib
import os
import random
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from loguru import logger

from cassandra_io import bulk_insert, connect
from excel_loader import (
    SUB_ALCALDIAS,
    TARIFA_HEADERS,
    clean_text,
    load_distritos_zonas,
    load_errores,
    load_modelos,
    load_tarifas,
    load_tipos_infra,
    load_workbook,
)

try:
    from passlib.context import CryptContext

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

except Exception:

    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()


PERIODO_DEFAULT = os.getenv("SEED_PERIODO", "2026-05")
TIPO_CAMBIO = Decimal(os.getenv("SEED_TIPO_CAMBIO", "6.96"))
SEED_RESET = os.getenv("SEED_RESET", "false").lower() in {"1", "true", "yes", "si"}
CONCURRENCY = int(os.getenv("SEED_CONCURRENCY", "80"))
CHUNK_SIZE = int(os.getenv("SEED_CHUNK_SIZE", "3000"))

TARGET_GATEWAYS = int(os.getenv("SEED_TARGET_GATEWAYS", "14"))
TARGET_INFRAESTRUCTURAS = int(os.getenv("SEED_TARGET_INFRAESTRUCTURAS", "80000"))
TARGET_CONTRATOS = int(os.getenv("SEED_TARGET_CONTRATOS", "100000"))
TARGET_MEDIDORES = int(os.getenv("SEED_TARGET_MEDIDORES", "120000"))

EXCEL_PATH = os.getenv("SEEDER_EXCEL", "/data/resources/recursos_practica_5.xlsx")
INFRA_CSV = os.getenv("SEED_INFRA_CSV", "/data/resources/infraestructuras_cochabamba.csv")
CONTRATOS_CSV = os.getenv("SEED_CONTRATOS_CSV", "/data/resources/contratos_agua.csv")
MEDIDORES_CSV = os.getenv("SEED_MEDIDORES_CSV", "/data/resources/medidores_iot.csv")

NAMESPACE = uuid.UUID("6fa459ea-ee8a-3ca4-894e-db77e160355e")


@dataclass(slots=True)
class InfraRow:
    infraestructura_id: uuid.UUID
    persona_id: uuid.UUID
    numero_catastro: str
    propietario: str
    ci: str
    tipo_infra: int
    distrito_id: int
    zona_id: int
    zona_nombre: str
    distrito_nombre: str
    direccion: str
    manzano: str
    lote: str
    superficie_terreno: Decimal
    area_construida: Decimal
    uso_suelo: str
    matricula_ddrr: str
    valor_catastral: Decimal
    impuesto_anual: Decimal
    latitud: float
    longitud: float


@dataclass(slots=True)
class ContratoRow:
    numero_contrato: int
    numero_catastro: str
    titular_contrato: str
    ci_titular: str
    categoria: str
    subcategoria: str
    medidor_iot: str
    fecha_contrato: date | None
    estado_contrato: str
    diametro_conexion: str
    tipo_servicio: str


@dataclass(slots=True)
class MedidorRow:
    medidor_id: uuid.UUID
    medidor_iot: str
    mac: str
    numero_serie: str
    numero_contrato: int | None
    numero_catastro: str
    infraestructura_id: uuid.UUID | None
    persona_id: uuid.UUID | None
    modelo_id: int
    tipo_medidor_id: int
    categoria_tarifa: str
    gateway_id: int
    distrito_id: int
    zona_id: int
    latitud: float
    longitud: float
    fecha_instalacion: date | None
    fecha_desinstalacion: date | None
    fecha_retiro: date | None
    estado: str
    motivo_estado: str
    medidor_anterior_id: uuid.UUID | None
    es_medidor_actual: bool


def norm_key(value: Any) -> str:
    text = clean_text(value).lower()
    text = (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def deterministic_uuid(prefix: str, value: Any) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{prefix}:{clean_text(value)}")


def as_decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    text = clean_text(value)
    text = text.replace("Bs.", "").replace("Bs", "").replace("$us", "").replace("USD", "")
    text = text.replace(" ", "").replace(",", ".")
    if not text:
        return Decimal(default)
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal(default)


def as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    text = clean_text(value).replace(",", ".")
    if not text:
        return default
    try:
        return int(float(text))
    except ValueError:
        found = re.search(r"\d+", text)
        return int(found.group(0)) if found else default


def as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def estado_medidor(value: Any) -> str:
    text = norm_key(value)
    if text in {"operativo", "activo", "nuevo", "reacondicionado", "instalado"}:
        return "ACTIVO"
    if text in {"danado", "fuera_servicio", "fuera_de_servicio", "fallado"}:
        return "FUERA_SERVICIO"
    if text in {"mantenimiento", "revision", "en_mantenimiento"}:
        return "MANTENIMIENTO"
    if text in {"retirado", "desinstalado", "baja"}:
        return "RETIRADO"
    if text in {"disponible", "stock", "almacen"}:
        return "DISPONIBLE"
    return "ACTIVO"


def estado_contrato(value: Any) -> str:
    text = norm_key(value)
    if text in {"activo", "vigente", "habilitado"}:
        return "ACTIVO"
    if text in {"suspendido", "cortado"}:
        return "SUSPENDIDO"
    if text in {"baja", "anulado", "inactivo"}:
        return "INACTIVO"
    if text in {"mora", "moroso"}:
        return "MORA"
    return "ACTIVO"


def categoria_tarifa(categoria: Any, subcategoria: Any = "") -> str:
    sub = clean_text(subcategoria).upper()
    cat = norm_key(categoria)
    if sub in TARIFA_HEADERS:
        return sub
    if cat.upper() in TARIFA_HEADERS:
        return cat.upper()
    if "resid" in cat or "domest" in cat:
        return "R3"
    if "comercial_especial" in cat or "especial" in cat:
        return "CE"
    if "comercial" in cat:
        return "C"
    if "industrial" in cat or cat == "industria":
        return "I"
    if "preferencial" in cat:
        return "P"
    if "social" in cat:
        return "S"
    return "R3"


def generated_email(name: str, doc: str) -> str:
    base = norm_key(name).replace("_", ".") or "usuario"
    suffix = re.sub(r"\D+", "", doc)[-4:] or str(abs(hash(doc)) % 9999).zfill(4)
    return f"{base}.{suffix}@demo.semapa.bo"


def generate_mac(seed: Any) -> str:
    h = hashlib.md5(clean_text(seed).encode("utf-8")).hexdigest().upper()
    return ":".join(h[i : i + 2] for i in range(0, 12, 2))


def generate_serie(seed: Any) -> str:
    h = hashlib.md5(clean_text(seed).encode("utf-8")).hexdigest().upper()
    return f"SN={int(h[:10], 16) % 9000000000 + 1000000000}"


def find_file(path_value: str, candidates: list[str]) -> Path:
    path = Path(path_value)
    if path.exists():
        return path
    search_dirs = [Path("/data/resources"), Path("/data"), Path("/recursos"), Path(".")]
    for base in search_dirs:
        for name in candidates:
            candidate = base / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(
        f"No se encontró archivo. Configurado={path_value}. Candidatos={candidates}. "
        "Ubica los archivos en data/resources."
    )


def open_csv_dict(path: Path) -> list[dict[str, str]]:
    encodings = ["utf-8-sig", "utf-8", "latin-1"]
    last_error: Exception | None = None
    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(f, dialect=dialect)
                rows: list[dict[str, str]] = []
                for row in reader:
                    normalized = {norm_key(k): clean_text(v) for k, v in row.items() if k is not None}
                    if any(v for v in normalized.values()):
                        rows.append(normalized)
                logger.info(f"CSV cargado: {path} | filas={len(rows):,}")
                return rows
        except Exception as e:
            last_error = e
    raise RuntimeError(f"No se pudo leer CSV {path}: {last_error}")


def insert_many(session, prepared, rows: Iterable[tuple], label: str) -> int:
    total = 0
    chunk: list[tuple] = []
    for row in rows:
        chunk.append(row)
        if len(chunk) >= CHUNK_SIZE:
            total += bulk_insert(session, prepared, chunk, concurrency=CONCURRENCY)
            logger.info(f"{label}: {total:,} filas insertadas")
            chunk.clear()
    if chunk:
        total += bulk_insert(session, prepared, chunk, concurrency=CONCURRENCY)
        logger.info(f"{label}: {total:,} filas insertadas")
    return total


def truncate_tables(session) -> None:
    tables = [
        "eventos_mensajeria",
        "pdfs_preaviso",
        "preavisos_por_contrato",
        "preavisos_por_periodo",
        "kiosk_consultas",
        "reclamos_por_contrato",
        "reclamos_ciudadanos",
        "resumen_dashboard_alcaldia",
        "resumen_dashboard_gerencia",
        "resumen_dashboard_contabilidad",
        "proyeccion_ingresos_por_categoria",
        "proyeccion_demanda_por_distrito",
        "facturas_por_categoria",
        "facturas_por_periodo",
        "facturas",
        "lecturas_manuales_por_usuario",
        "lecturas_manuales",
        "lecturas_raw",
        "lecturas_por_zona_dia",
        "lecturas_por_medidor",
        "cobertura_gateway",
        "medidores_por_estado_zona",
        "medidores_por_serie",
        "medidores_por_mac",
        "medidores_por_contrato",
        "medidores_por_iot",
        "medidores",
        "contratos_por_estado",
        "contratos_por_medidor",
        "contratos_por_catastro",
        "contratos_por_ci",
        "contratos",
        "infraestructuras_por_zona",
        "infraestructuras_por_catastro",
        "infraestructuras",
        "personas_por_documento",
        "personas",
        "usuarios_sistema",
        "errores_iot",
        "tipos_infraestructura",
        "tarifas",
        "modelos_medidor",
        "gateways",
        "zonas",
        "distritos",
        "sub_alcaldias",
    ]
    for table in tables:
        try:
            logger.info(f"TRUNCATE {table}")
            session.execute(f"TRUNCATE {table}")
        except Exception as e:
            logger.warning(f"No se pudo truncar {table}: {e}")


def fallback_lat_lon(distrito_id: int, zona_id: int) -> tuple[float, float]:
    base_lat = -17.3895
    base_lon = -66.1568
    lat = base_lat + ((int(distrito_id) % 7) - 3) * 0.009 + ((int(zona_id) % 5) - 2) * 0.002
    lon = base_lon + ((int(distrito_id) % 6) - 3) * 0.010 + ((int(zona_id) % 7) - 3) * 0.002
    return round(lat, 6), round(lon, 6)


def generate_gateways(target: int) -> list[tuple[int, str, float, float]]:
    base_points = [
        ("LoRaWan-Teleferico", -17.389222, -66.141722),
        ("LoRaWan-ParqueVial", -17.381000, -66.153361),
        ("LoRaWan-ParqueLincoln", -17.369861, -66.176389),
        ("LoRaWan-Petrolera", -17.444083, -66.140694),
        ("LoRaWan-SurEste", -17.420000, -66.110000),
        ("LoRaWan-Norte", -17.350000, -66.170000),
        ("LoRaWan-Centro", -17.393000, -66.157000),
        ("LoRaWan-Itocta", -17.450000, -66.180000),
        ("LoRaWan-AdelaZamudio", -17.389000, -66.161000),
        ("LoRaWan-ValleHermoso", -17.410000, -66.155000),
        ("LoRaWan-AlejoCalatayud", -17.405000, -66.135000),
        ("LoRaWan-Molle", -17.377000, -66.185000),
        ("LoRaWan-Tunari", -17.355000, -66.145000),
        ("LoRaWan-LagunaAlalay", -17.410000, -66.135000),
    ]
    out: list[tuple[int, str, float, float]] = []
    for i in range(target):
        name, lat, lon = base_points[i % len(base_points)]
        if i >= len(base_points):
            lat += (i // len(base_points)) * 0.002
            lon -= (i // len(base_points)) * 0.002
        out.append((i + 1, name, round(lat, 6), round(lon, 6)))
    return out


def build_zone_indexes(zonas) -> tuple[dict[tuple[int, int], Any], dict[str, list[Any]], list[Any]]:
    by_key = {(z.distrito_id, z.zona_id): z for z in zonas}
    by_name: dict[str, list[Any]] = defaultdict(list)
    for z in zonas:
        by_name[norm_key(z.nombre)].append(z)
    return by_key, by_name, list(zonas)


def resolve_zone(row: dict[str, str], index: int, zones_by_name: dict[str, list[Any]], zones_list: list[Any]) -> Any:
    distrito_raw = row.get("distrito") or row.get("distrito_id") or row.get("distrito_nombre")
    zona_raw = row.get("zona") or row.get("zona_nombre") or row.get("subdistrito")
    distrito_id = as_int(distrito_raw, 0)
    zona_name = norm_key(zona_raw)
    if zona_name in zones_by_name:
        matches = zones_by_name[zona_name]
        if distrito_id:
            for z in matches:
                if z.distrito_id == distrito_id:
                    return z
        return matches[0]
    if zones_list:
        return zones_list[index % len(zones_list)]
    raise RuntimeError("No existen zonas cargadas desde el Excel.")


def normalize_infra_rows(csv_rows: list[dict[str, str]], zones_by_name, zones_list) -> list[InfraRow]:
    out: list[InfraRow] = []
    for i, row in enumerate(csv_rows[:TARGET_INFRAESTRUCTURAS]):
        numero_catastro = row.get("numero_catastro") or row.get("catastro") or row.get("nro_catastro") or f"CAT-{i + 1:08d}"
        propietario = row.get("propietario") or row.get("titular") or row.get("nombre") or f"Propietario {i + 1}"
        ci = row.get("ci") or row.get("documento") or row.get("ci_nit") or str(5000000 + i)
        direccion = row.get("direccion") or f"Dirección referencial Nro {i + 1}"
        zone = resolve_zone(row, i, zones_by_name, zones_list)
        distrito_id = int(zone.distrito_id)
        zona_id = int(zone.zona_id)
        lat = float(as_decimal(row.get("latitud"), "0"))
        lon = float(as_decimal(row.get("longitud"), "0"))
        if lat == 0 or lon == 0:
            lat, lon = fallback_lat_lon(distrito_id, zona_id)
        infraestructura_id = deterministic_uuid("infraestructura", numero_catastro)
        persona_id = deterministic_uuid("persona", ci)
        out.append(
            InfraRow(
                infraestructura_id=infraestructura_id,
                persona_id=persona_id,
                numero_catastro=clean_text(numero_catastro),
                propietario=clean_text(propietario),
                ci=clean_text(ci),
                tipo_infra=1,
                distrito_id=distrito_id,
                zona_id=zona_id,
                zona_nombre=clean_text(row.get("zona") or zone.nombre),
                distrito_nombre=clean_text(row.get("distrito") or f"DISTRITO {distrito_id}"),
                direccion=clean_text(direccion),
                manzano=clean_text(row.get("manzano")),
                lote=clean_text(row.get("lote")),
                superficie_terreno=as_decimal(row.get("superficie_terreno")),
                area_construida=as_decimal(row.get("area_construida")),
                uso_suelo=clean_text(row.get("uso_suelo") or "Residencial"),
                matricula_ddrr=clean_text(row.get("matricula_ddrr")),
                valor_catastral=as_decimal(row.get("valor_catastral")),
                impuesto_anual=as_decimal(row.get("impuesto_anual")),
                latitud=lat,
                longitud=lon,
            )
        )
    logger.info(f"Infraestructuras normalizadas: {len(out):,}")
    return out


def normalize_contrato_rows(csv_rows: list[dict[str, str]]) -> list[ContratoRow]:
    out: list[ContratoRow] = []
    for i, row in enumerate(csv_rows[:TARGET_CONTRATOS]):
        numero_contrato = as_int(row.get("numero_contrato") or row.get("contrato"), 100000000 + i)
        numero_catastro = row.get("numero_catastro") or row.get("catastro") or ""
        titular = row.get("titular_contrato") or row.get("titular") or row.get("propietario") or f"Titular {i + 1}"
        ci_titular = row.get("ci_titular") or row.get("ci") or row.get("nit") or str(5000000 + i)
        categoria = categoria_tarifa(row.get("categoria"), row.get("subcategoria"))
        out.append(
            ContratoRow(
                numero_contrato=numero_contrato,
                numero_catastro=clean_text(numero_catastro),
                titular_contrato=clean_text(titular),
                ci_titular=clean_text(ci_titular),
                categoria=categoria,
                subcategoria=categoria,
                medidor_iot=clean_text(row.get("medidor_iot") or row.get("medidor") or row.get("macmedidor")),
                fecha_contrato=as_date(row.get("fecha_contrato")) or date(2024, 1, 1) + timedelta(days=i % 420),
                estado_contrato=estado_contrato(row.get("estado_contrato")),
                diametro_conexion=clean_text(row.get("diametro_conexion") or "1/2"),
                tipo_servicio=clean_text(row.get("tipo_servicio") or "AGUA POTABLE"),
            )
        )
    logger.info(f"Contratos normalizados: {len(out):,}")
    return out


def normalize_medidor_rows(
    csv_rows: list[dict[str, str]],
    contratos_by_medidor: dict[str, ContratoRow],
    infra_by_catastro: dict[str, InfraRow],
    zones_list: list[Any],
) -> list[MedidorRow]:
    out: list[MedidorRow] = []
    rnd = random.Random(202605)
    for i, row in enumerate(csv_rows[:TARGET_MEDIDORES]):
        medidor_iot = clean_text(row.get("medidor_iot") or row.get("macmedidor") or row.get("medidor") or f"IOT-{i + 1:012d}")
        contrato = contratos_by_medidor.get(medidor_iot)
        numero_contrato = contrato.numero_contrato if contrato else None
        numero_catastro = contrato.numero_catastro if contrato else ""
        categoria = contrato.categoria if contrato else "R3"
        infra = infra_by_catastro.get(numero_catastro) if numero_catastro else None
        if infra:
            infraestructura_id = infra.infraestructura_id
            persona_id = infra.persona_id
            distrito_id = infra.distrito_id
            zona_id = infra.zona_id
            lat = infra.latitud
            lon = infra.longitud
        else:
            zone = zones_list[i % len(zones_list)]
            infraestructura_id = None
            persona_id = None
            distrito_id = int(zone.distrito_id)
            zona_id = int(zone.zona_id)
            lat, lon = fallback_lat_lon(distrito_id, zona_id)
        tipo_medidor_id = as_int(row.get("tipo_medidor_id") or row.get("modelo_id"), (i % 5) + 1)
        modelo_id = tipo_medidor_id if 1 <= tipo_medidor_id <= 5 else ((i % 5) + 1)
        gateway_id = ((distrito_id + zona_id + i) % TARGET_GATEWAYS) + 1
        estado = estado_medidor(row.get("estado"))
        fecha_instalacion = as_date(row.get("fecha_instalacion")) or date(2020, 1, 1) + timedelta(days=i % 1887)
        fecha_desinstalacion = as_date(row.get("fecha_desinstalacion"))
        fecha_retiro = fecha_desinstalacion
        es_actual = False if fecha_desinstalacion else estado in {"ACTIVO", "MANTENIMIENTO", "DISPONIBLE"}
        lat += rnd.uniform(-0.0008, 0.0008)
        lon += rnd.uniform(-0.0008, 0.0008)
        out.append(
            MedidorRow(
                medidor_id=deterministic_uuid("medidor", medidor_iot),
                medidor_iot=medidor_iot,
                mac=generate_mac(medidor_iot),
                numero_serie=generate_serie(medidor_iot),
                numero_contrato=numero_contrato,
                numero_catastro=numero_catastro,
                infraestructura_id=infraestructura_id,
                persona_id=persona_id,
                modelo_id=modelo_id,
                tipo_medidor_id=tipo_medidor_id,
                categoria_tarifa=categoria,
                gateway_id=gateway_id,
                distrito_id=distrito_id,
                zona_id=zona_id,
                latitud=round(lat, 6),
                longitud=round(lon, 6),
                fecha_instalacion=fecha_instalacion,
                fecha_desinstalacion=fecha_desinstalacion,
                fecha_retiro=fecha_retiro,
                estado=estado,
                motivo_estado="" if estado == "ACTIVO" else estado,
                medidor_anterior_id=None,
                es_medidor_actual=es_actual,
            )
        )
    logger.info(f"Medidores normalizados: {len(out):,}")
    return out


def seed_catalogos(session, wb) -> list[Any]:
    logger.info("Insertando catálogos...")
    distritos, zonas = load_distritos_zonas(wb)
    tarifas = load_tarifas(wb)
    modelos = load_modelos(wb)
    errores = load_errores(wb)
    tipos = load_tipos_infra(wb)

    ps_sub = session.prepare("INSERT INTO sub_alcaldias (sub_alcaldia_id, nombre) VALUES (?, ?)")
    ps_dist = session.prepare("INSERT INTO distritos (distrito_id, sub_alcaldia_id, nombre, habitantes) VALUES (?, ?, ?, ?)")
    ps_zona = session.prepare("INSERT INTO zonas (distrito_id, zona_id, nombre, gateway_id) VALUES (?, ?, ?, ?)")
    ps_gw = session.prepare("INSERT INTO gateways (gateway_id, nombre, latitud, longitud) VALUES (?, ?, ?, ?)")
    ps_mod = session.prepare("INSERT INTO modelos_medidor (modelo_id, marca, modelo, conectividad, aplicacion) VALUES (?, ?, ?, ?, ?)")
    ps_tar = session.prepare(
        """
        INSERT INTO tarifas (
            categoria, alias, fijo_m3, usd_mes, r_13_25, r_26_50, r_51_75,
            r_76_100, r_101_150, r_mas_151, descripcion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_err = session.prepare("INSERT INTO errores_iot (codigo, descripcion) VALUES (?, ?)")
    ps_tipo = session.prepare("INSERT INTO tipos_infraestructura (tipo_id, descripcion) VALUES (?, ?)")

    insert_many(session, ps_sub, ((sid, name) for sid, name in SUB_ALCALDIAS), "sub_alcaldias")
    insert_many(session, ps_dist, ((d.distrito_id, d.sub_alcaldia_id, d.nombre, d.habitantes) for d in distritos), "distritos")
    insert_many(session, ps_zona, ((z.distrito_id, z.zona_id, z.nombre, ((z.gateway_id - 1) % TARGET_GATEWAYS) + 1) for z in zonas), "zonas")
    insert_many(session, ps_gw, generate_gateways(TARGET_GATEWAYS), "gateways")
    insert_many(session, ps_mod, ((m.modelo_id, m.marca, m.modelo, m.conectividad, m.aplicacion) for m in modelos), "modelos_medidor")
    insert_many(
        session,
        ps_tar,
        (
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
        ),
        "tarifas",
    )
    insert_many(session, ps_err, ((c, d) for c, d in errores), "errores_iot")
    insert_many(session, ps_tipo, ((t.tipo_id, t.descripcion) for t in tipos), "tipos_infraestructura")
    return zonas


def seed_personas(session, infra_rows: list[InfraRow], contrato_rows: list[ContratoRow]) -> None:
    logger.info("Insertando personas...")
    people: dict[str, dict[str, Any]] = {}
    for infra in infra_rows:
        if infra.ci:
            people[infra.ci] = {
                "persona_id": infra.persona_id,
                "tipo": "NATURAL",
                "documento": infra.ci,
                "nombre": infra.propietario,
                "apellidos": "",
                "razon_social": "",
                "email": generated_email(infra.propietario, infra.ci),
                "telefono": "",
                "fecha_registro": datetime.utcnow(),
            }
    for contrato in contrato_rows:
        if contrato.ci_titular and contrato.ci_titular not in people:
            people[contrato.ci_titular] = {
                "persona_id": deterministic_uuid("persona", contrato.ci_titular),
                "tipo": "NATURAL",
                "documento": contrato.ci_titular,
                "nombre": contrato.titular_contrato,
                "apellidos": "",
                "razon_social": "",
                "email": generated_email(contrato.titular_contrato, contrato.ci_titular),
                "telefono": "",
                "fecha_registro": datetime.utcnow(),
            }

    ps_persona = session.prepare(
        """
        INSERT INTO personas (
            persona_id, tipo, documento, nombre, apellidos, razon_social,
            email, telefono, fecha_registro
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_doc = session.prepare(
        """
        INSERT INTO personas_por_documento (
            documento, persona_id, tipo, nombre, apellidos, razon_social, email, telefono
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    insert_many(
        session,
        ps_persona,
        ((p["persona_id"], p["tipo"], p["documento"], p["nombre"], p["apellidos"], p["razon_social"], p["email"], p["telefono"], p["fecha_registro"]) for p in people.values()),
        "personas",
    )
    insert_many(
        session,
        ps_doc,
        ((p["documento"], p["persona_id"], p["tipo"], p["nombre"], p["apellidos"], p["razon_social"], p["email"], p["telefono"]) for p in people.values()),
        "personas_por_documento",
    )
    logger.info(f"Personas únicas insertadas: {len(people):,}")


def seed_infraestructuras(session, infra_rows: list[InfraRow]) -> None:
    logger.info("Insertando infraestructuras...")
    ps = session.prepare(
        """
        INSERT INTO infraestructuras (
            infraestructura_id, persona_id, numero_catastro, propietario, ci, tipo_infra,
            distrito_id, zona_id, zona_nombre, distrito_nombre, direccion, manzano, lote,
            superficie_terreno, area_construida, uso_suelo, matricula_ddrr,
            valor_catastral, impuesto_anual, latitud, longitud
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_cat = session.prepare(
        """
        INSERT INTO infraestructuras_por_catastro (
            numero_catastro, infraestructura_id, persona_id, propietario, ci, direccion,
            zona, distrito, distrito_id, zona_id, manzano, lote, superficie_terreno,
            area_construida, uso_suelo, matricula_ddrr, valor_catastral,
            impuesto_anual, latitud, longitud
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_zona = session.prepare(
        """
        INSERT INTO infraestructuras_por_zona (
            distrito_id, zona_id, numero_catastro, infraestructura_id, propietario,
            ci, direccion, uso_suelo, latitud, longitud
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    insert_many(
        session,
        ps,
        ((r.infraestructura_id, r.persona_id, r.numero_catastro, r.propietario, r.ci, r.tipo_infra, r.distrito_id, r.zona_id, r.zona_nombre, r.distrito_nombre, r.direccion, r.manzano, r.lote, r.superficie_terreno, r.area_construida, r.uso_suelo, r.matricula_ddrr, r.valor_catastral, r.impuesto_anual, r.latitud, r.longitud) for r in infra_rows),
        "infraestructuras",
    )
    insert_many(
        session,
        ps_cat,
        ((r.numero_catastro, r.infraestructura_id, r.persona_id, r.propietario, r.ci, r.direccion, r.zona_nombre, r.distrito_nombre, r.distrito_id, r.zona_id, r.manzano, r.lote, r.superficie_terreno, r.area_construida, r.uso_suelo, r.matricula_ddrr, r.valor_catastral, r.impuesto_anual, r.latitud, r.longitud) for r in infra_rows),
        "infraestructuras_por_catastro",
    )
    insert_many(
        session,
        ps_zona,
        ((r.distrito_id, r.zona_id, r.numero_catastro, r.infraestructura_id, r.propietario, r.ci, r.direccion, r.uso_suelo, r.latitud, r.longitud) for r in infra_rows),
        "infraestructuras_por_zona",
    )


def seed_contratos(session, contrato_rows: list[ContratoRow]) -> None:
    logger.info("Insertando contratos...")
    now = datetime.utcnow()
    ps = session.prepare(
        """
        INSERT INTO contratos (
            numero_contrato, numero_catastro, titular_contrato, ci_titular,
            categoria, subcategoria, medidor_iot, fecha_contrato, estado_contrato,
            diametro_conexion, tipo_servicio, fecha_carga
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_ci = session.prepare(
        """
        INSERT INTO contratos_por_ci (
            ci_titular, numero_contrato, numero_catastro, titular_contrato,
            categoria, subcategoria, medidor_iot, estado_contrato, fecha_contrato
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_catastro = session.prepare(
        """
        INSERT INTO contratos_por_catastro (
            numero_catastro, numero_contrato, titular_contrato, ci_titular,
            categoria, subcategoria, medidor_iot, estado_contrato, fecha_contrato
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_medidor = session.prepare(
        """
        INSERT INTO contratos_por_medidor (
            medidor_iot, numero_contrato, numero_catastro, titular_contrato,
            ci_titular, categoria, subcategoria, estado_contrato, fecha_contrato
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_estado = session.prepare(
        """
        INSERT INTO contratos_por_estado (
            estado_contrato, categoria, numero_contrato, titular_contrato,
            ci_titular, numero_catastro, medidor_iot, fecha_contrato
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    insert_many(session, ps, ((r.numero_contrato, r.numero_catastro, r.titular_contrato, r.ci_titular, r.categoria, r.subcategoria, r.medidor_iot, r.fecha_contrato, r.estado_contrato, r.diametro_conexion, r.tipo_servicio, now) for r in contrato_rows), "contratos")
    insert_many(session, ps_ci, ((r.ci_titular, r.numero_contrato, r.numero_catastro, r.titular_contrato, r.categoria, r.subcategoria, r.medidor_iot, r.estado_contrato, r.fecha_contrato) for r in contrato_rows), "contratos_por_ci")
    insert_many(session, ps_catastro, ((r.numero_catastro, r.numero_contrato, r.titular_contrato, r.ci_titular, r.categoria, r.subcategoria, r.medidor_iot, r.estado_contrato, r.fecha_contrato) for r in contrato_rows), "contratos_por_catastro")
    insert_many(session, ps_medidor, ((r.medidor_iot, r.numero_contrato, r.numero_catastro, r.titular_contrato, r.ci_titular, r.categoria, r.subcategoria, r.estado_contrato, r.fecha_contrato) for r in contrato_rows if r.medidor_iot), "contratos_por_medidor")
    insert_many(session, ps_estado, ((r.estado_contrato, r.categoria, r.numero_contrato, r.titular_contrato, r.ci_titular, r.numero_catastro, r.medidor_iot, r.fecha_contrato) for r in contrato_rows), "contratos_por_estado")


def seed_medidores(session, medidor_rows: list[MedidorRow]) -> None:
    logger.info("Insertando medidores...")
    ps = session.prepare(
        """
        INSERT INTO medidores (
            medidor_id, medidor_iot, mac, numero_serie, numero_contrato,
            numero_catastro, infraestructura_id, persona_id, modelo_id,
            tipo_medidor_id, categoria_tarifa, gateway_id, distrito_id, zona_id,
            latitud, longitud, fecha_instalacion, fecha_desinstalacion,
            fecha_retiro, estado, motivo_estado, medidor_anterior_id,
            es_medidor_actual
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_iot = session.prepare(
        """
        INSERT INTO medidores_por_iot (
            medidor_iot, medidor_id, mac, numero_serie, numero_contrato,
            numero_catastro, modelo_id, tipo_medidor_id, categoria_tarifa,
            gateway_id, distrito_id, zona_id, latitud, longitud,
            fecha_instalacion, fecha_desinstalacion, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_contrato = session.prepare(
        """
        INSERT INTO medidores_por_contrato (
            numero_contrato, medidor_id, medidor_iot, mac, numero_serie,
            numero_catastro, modelo_id, tipo_medidor_id, categoria_tarifa,
            gateway_id, distrito_id, zona_id, latitud, longitud, estado,
            es_medidor_actual
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_mac = session.prepare(
        """
        INSERT INTO medidores_por_mac (
            mac, medidor_id, medidor_iot, numero_serie, numero_contrato,
            numero_catastro, modelo_id, tipo_medidor_id, categoria_tarifa,
            gateway_id, distrito_id, zona_id, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_serie = session.prepare(
        """
        INSERT INTO medidores_por_serie (
            numero_serie, medidor_id, medidor_iot, mac, numero_contrato,
            numero_catastro, modelo_id, tipo_medidor_id, categoria_tarifa,
            gateway_id, distrito_id, zona_id, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_estado = session.prepare(
        """
        INSERT INTO medidores_por_estado_zona (
            estado, distrito_id, zona_id, medidor_id, medidor_iot,
            numero_serie, numero_contrato, categoria_tarifa, gateway_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    insert_many(session, ps, ((r.medidor_id, r.medidor_iot, r.mac, r.numero_serie, r.numero_contrato, r.numero_catastro, r.infraestructura_id, r.persona_id, r.modelo_id, r.tipo_medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id, r.latitud, r.longitud, r.fecha_instalacion, r.fecha_desinstalacion, r.fecha_retiro, r.estado, r.motivo_estado, r.medidor_anterior_id, r.es_medidor_actual) for r in medidor_rows), "medidores")
    insert_many(session, ps_iot, ((r.medidor_iot, r.medidor_id, r.mac, r.numero_serie, r.numero_contrato, r.numero_catastro, r.modelo_id, r.tipo_medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id, r.latitud, r.longitud, r.fecha_instalacion, r.fecha_desinstalacion, r.estado) for r in medidor_rows), "medidores_por_iot")
    insert_many(session, ps_contrato, ((r.numero_contrato, r.medidor_id, r.medidor_iot, r.mac, r.numero_serie, r.numero_catastro, r.modelo_id, r.tipo_medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id, r.latitud, r.longitud, r.estado, r.es_medidor_actual) for r in medidor_rows if r.numero_contrato is not None), "medidores_por_contrato")
    insert_many(session, ps_mac, ((r.mac, r.medidor_id, r.medidor_iot, r.numero_serie, r.numero_contrato, r.numero_catastro, r.modelo_id, r.tipo_medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id, r.estado) for r in medidor_rows), "medidores_por_mac")
    insert_many(session, ps_serie, ((r.numero_serie, r.medidor_id, r.medidor_iot, r.mac, r.numero_contrato, r.numero_catastro, r.modelo_id, r.tipo_medidor_id, r.categoria_tarifa, r.gateway_id, r.distrito_id, r.zona_id, r.estado) for r in medidor_rows), "medidores_por_serie")
    insert_many(session, ps_estado, ((r.estado, r.distrito_id, r.zona_id, r.medidor_id, r.medidor_iot, r.numero_serie, r.numero_contrato, r.categoria_tarifa, r.gateway_id) for r in medidor_rows), "medidores_por_estado_zona")


def calc_monto_usd(tarifa, consumo_m3: Decimal) -> Decimal:
    if tarifa is None:
        return (Decimal("2.50") + consumo_m3 * Decimal("0.18")).quantize(Decimal("0.01"))
    total = Decimal(tarifa.usd_mes or 0)
    fijo = Decimal(tarifa.fijo_m3 or 0)
    if consumo_m3 <= fijo:
        return max(total, Decimal("1.00")).quantize(Decimal("0.01"))
    remaining = consumo_m3 - fijo
    if remaining > 0:
        total += min(remaining, Decimal("13")) * Decimal(tarifa.r_13_25 or 0)
    if consumo_m3 > Decimal("25"):
        total += (min(consumo_m3, Decimal("50")) - Decimal("25")) * Decimal(tarifa.r_26_50 or 0)
    if consumo_m3 > Decimal("50"):
        total += (min(consumo_m3, Decimal("75")) - Decimal("50")) * Decimal(tarifa.r_51_75 or 0)
    if consumo_m3 > Decimal("75"):
        total += (min(consumo_m3, Decimal("100")) - Decimal("75")) * Decimal(tarifa.r_76_100 or 0)
    if consumo_m3 > Decimal("100"):
        total += (min(consumo_m3, Decimal("150")) - Decimal("100")) * Decimal(tarifa.r_101_150 or 0)
    if consumo_m3 > Decimal("150"):
        total += (consumo_m3 - Decimal("150")) * Decimal(tarifa.r_mas_151 or 0)
    if total <= 0:
        total = Decimal("2.50") + consumo_m3 * Decimal("0.18")
    return total.quantize(Decimal("0.01"))


def seed_facturas_y_resumenes(session, medidores: list[MedidorRow], contratos: list[ContratoRow], zonas, wb) -> None:
    logger.info("Generando facturas y resúmenes para dashboards...")
    tarifas = {t.categoria: t for t in load_tarifas(wb)}
    medidores_con_contrato = [m for m in medidores if m.numero_contrato is not None]
    medidor_by_contrato = {m.numero_contrato: m for m in medidores_con_contrato}
    ps_factura = session.prepare(
        """
        INSERT INTO facturas (
            numero_contrato, periodo, factura_id, medidor_id, persona_id,
            consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa,
            desglose, fecha_emision, estado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_periodo = session.prepare(
        """
        INSERT INTO facturas_por_periodo (
            periodo, distrito_id, numero_contrato, monto_usd, monto_bs,
            consumo_m3, categoria_tarifa, estado, fecha_emision
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_categoria = session.prepare(
        """
        INSERT INTO facturas_por_categoria (
            periodo, categoria_tarifa, numero_contrato, monto_bs, consumo_m3, estado
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
    )
    facturas = []
    for i, m in enumerate(medidores_con_contrato):
        consumo_m3 = Decimal(8 + ((m.distrito_id * 3 + m.zona_id * 5 + i) % 85))
        monto_usd = calc_monto_usd(tarifas.get(m.categoria_tarifa), consumo_m3)
        monto_bs = (monto_usd * TIPO_CAMBIO).quantize(Decimal("0.01"))
        estado = "MORA" if i % 13 == 0 else ("PENDIENTE" if i % 5 == 0 else "PAGADA")
        facturas.append((m.numero_contrato, PERIODO_DEFAULT, deterministic_uuid("factura", f"{m.numero_contrato}:{PERIODO_DEFAULT}"), m.medidor_id, m.persona_id, consumo_m3, monto_usd, monto_bs, TIPO_CAMBIO, m.categoria_tarifa, f'{{"periodo":"{PERIODO_DEFAULT}","categoria":"{m.categoria_tarifa}"}}', datetime.utcnow(), estado))
    insert_many(session, ps_factura, facturas, "facturas")
    insert_many(session, ps_periodo, ((PERIODO_DEFAULT, medidor_by_contrato[f[0]].distrito_id, f[0], f[6], f[7], f[5], f[9], f[12], f[11]) for f in facturas if f[0] in medidor_by_contrato), "facturas_por_periodo")
    insert_many(session, ps_categoria, ((PERIODO_DEFAULT, f[9], f[0], f[7], f[5], f[12]) for f in facturas), "facturas_por_categoria")

    by_zone: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_contabilidad: dict[tuple[int, str], dict[str, Decimal | int]] = defaultdict(lambda: defaultdict(Decimal))
    for m in medidores:
        key = (m.distrito_id, m.zona_id)
        by_zone[key]["medidores_totales"] += 1
        if m.estado == "ACTIVO":
            by_zone[key]["medidores_activos"] += 1
        if m.estado in {"FUERA_SERVICIO", "MANTENIMIENTO", "RETIRADO"}:
            by_zone[key]["sensores_con_fallas"] += 1
    for f in facturas:
        medidor = medidor_by_contrato.get(f[0])
        if not medidor:
            continue
        key = (medidor.distrito_id, f[9])
        by_contabilidad[key]["monto_facturado_bs"] += f[7]
        by_contabilidad[key]["contratos_activos"] += 1
        if f[12] == "MORA":
            by_contabilidad[key]["cartera_vencida_bs"] += f[7]
            by_contabilidad[key]["contratos_morosos"] += 1
    zone_pop = {(z.distrito_id, z.zona_id): z.habitantes for z in zonas}

    ps_alcaldia = session.prepare(
        """
        INSERT INTO resumen_dashboard_alcaldia (
            periodo, distrito_id, zona_id, poblacion_beneficiaria, medidores_totales,
            medidores_activos, sensores_con_fallas, consumo_total_m3,
            consumo_per_capita_litros, cobertura_servicio, zonas_criticas,
            fecha_actualizacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_gerencia = session.prepare(
        """
        INSERT INTO resumen_dashboard_gerencia (
            periodo, distrito_id, zona_id, consumo_total_m3, consumo_promedio_diario_m3,
            pico_maximo_horario_m3, medidores_activos, medidores_inactivos,
            medidores_fuera_servicio, medidores_con_error, lecturas_faltantes,
            lecturas_app_movil, latencia_ingestion_ms, fecha_actualizacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_conta = session.prepare(
        """
        INSERT INTO resumen_dashboard_contabilidad (
            periodo, distrito_id, categoria_tarifa, monto_facturado_bs,
            monto_recaudado_bs, cartera_vencida_bs, contratos_activos,
            contratos_morosos, preavisos_emitidos, preavisos_entregados,
            preavisos_fallidos, ticket_promedio_bs, fecha_actualizacion
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )

    def alcaldia_rows():
        for (d, z), agg in by_zone.items():
            total = int(agg["medidores_totales"])
            activos = int(agg["medidores_activos"])
            fallas = int(agg["sensores_con_fallas"])
            poblacion = int(zone_pop.get((d, z), 0)) or total * 4
            consumo_total = Decimal(total * (12 + (d + z) % 7))
            consumo_pc = (consumo_total * Decimal("1000") / Decimal(max(poblacion, 1))).quantize(Decimal("0.01"))
            cobertura = (Decimal(activos) * Decimal("100") / Decimal(max(total, 1))).quantize(Decimal("0.01"))
            zonas_criticas = 1 if consumo_pc > Decimal("300") or fallas > total * 0.1 else 0
            yield (PERIODO_DEFAULT, d, z, poblacion, total, activos, fallas, consumo_total, consumo_pc, cobertura, zonas_criticas, datetime.utcnow())

    def gerencia_rows():
        for (d, z), agg in by_zone.items():
            total = int(agg["medidores_totales"])
            activos = int(agg["medidores_activos"])
            fallas = int(agg["sensores_con_fallas"])
            consumo_total = Decimal(total * (12 + (d + z) % 7))
            promedio = (consumo_total / Decimal("30")).quantize(Decimal("0.01"))
            pico = (promedio * Decimal("1.35")).quantize(Decimal("0.01"))
            yield (PERIODO_DEFAULT, d, z, consumo_total, promedio, pico, activos, max(total - activos - fallas, 0), fallas, fallas, int(total * 0.01), 0, Decimal(80 + ((d + z) % 30)), datetime.utcnow())

    def contabilidad_rows():
        for (d, categoria), agg in by_contabilidad.items():
            monto_facturado = Decimal(agg["monto_facturado_bs"])
            cartera = Decimal(agg["cartera_vencida_bs"])
            activos = int(agg["contratos_activos"])
            morosos = int(agg["contratos_morosos"])
            recaudado = monto_facturado - cartera
            ticket = (monto_facturado / Decimal(max(activos, 1))).quantize(Decimal("0.01"))
            yield (PERIODO_DEFAULT, d, categoria, monto_facturado.quantize(Decimal("0.01")), recaudado.quantize(Decimal("0.01")), cartera.quantize(Decimal("0.01")), activos, morosos, activos, int(activos * 0.92), int(activos * 0.08), ticket, datetime.utcnow())

    insert_many(session, ps_alcaldia, alcaldia_rows(), "resumen_dashboard_alcaldia")
    insert_many(session, ps_gerencia, gerencia_rows(), "resumen_dashboard_gerencia")
    insert_many(session, ps_conta, contabilidad_rows(), "resumen_dashboard_contabilidad")
    seed_proyecciones(session, by_contabilidad)


def seed_proyecciones(session, by_contabilidad) -> None:
    ps_ingresos = session.prepare(
        """
        INSERT INTO proyeccion_ingresos_por_categoria (
            periodo, categoria_tarifa, consumo_m3, ingresos_estimados_bs,
            ingresos_estimados_usd, contratos, fecha_calculo
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
    )
    ps_demanda = session.prepare(
        """
        INSERT INTO proyeccion_demanda_por_distrito (
            distrito_id, anio, consumo_proyectado_m3, factor_crecimiento,
            poblacion_estimada, fecha_calculo
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
    )
    cat_summary: dict[str, dict[str, Decimal | int]] = defaultdict(lambda: defaultdict(Decimal))
    for (_d, cat), agg in by_contabilidad.items():
        cat_summary[cat]["ingresos"] += Decimal(agg["monto_facturado_bs"])
        cat_summary[cat]["contratos"] += int(agg["contratos_activos"])
    insert_many(session, ps_ingresos, ((PERIODO_DEFAULT, cat, Decimal(int(vals["contratos"]) * 18), Decimal(vals["ingresos"]).quantize(Decimal("0.01")), (Decimal(vals["ingresos"]) / TIPO_CAMBIO).quantize(Decimal("0.01")), int(vals["contratos"]), datetime.utcnow()) for cat, vals in cat_summary.items()), "proyeccion_ingresos_por_categoria")
    demanda_rows = []
    for distrito_id in range(1, 16):
        base = Decimal(30000 + distrito_id * 2300)
        poblacion = 25000 + distrito_id * 3500
        for anio in range(2026, 2031):
            years = anio - 2026
            factor = Decimal("1.026") ** years
            demanda_rows.append((distrito_id, anio, (base * factor).quantize(Decimal("0.01")), Decimal("2.6"), int(poblacion * float(factor)), datetime.utcnow()))
    insert_many(session, ps_demanda, demanda_rows, "proyeccion_demanda_por_distrito")


def seed_cobertura(session, medidores: list[MedidorRow]) -> None:
    ps = session.prepare("INSERT INTO cobertura_gateway (gateway_id, zona_id, medidor_id, ultima_lectura) VALUES (?, ?, ?, ?)")
    insert_many(session, ps, ((m.gateway_id, m.zona_id, m.medidor_id, datetime.utcnow() - timedelta(hours=(m.distrito_id + m.zona_id) % 48)) for m in medidores if m.estado == "ACTIVO"), "cobertura_gateway")


def seed_usuarios(session) -> None:
    logger.info("Insertando usuarios del sistema...")
    users = [
        ("alcaldia", "Alcaldia2025!", "ALCALDIA", "Alcaldía Cochabamba", "alcaldia@semapa.bo"),
        ("gerencia", "Gerencia2025!", "GERENCIA", "Gerencia SEMAPA", "gerencia@semapa.bo"),
        ("contabilidad", "Contab2025!", "CONTABILIDAD", "Contabilidad SEMAPA", "contabilidad@semapa.bo"),
        ("admin", "12345", "ALCALDIA", "Administrador Alcaldía", "admin@semapa.bo"),
        ("gerente", "semapa2025", "GERENCIA", "Gerente SEMAPA", "gerente@semapa.bo"),
        ("contador", "finanzas2025", "CONTABILIDAD", "Contador SEMAPA", "contador@semapa.bo"),
    ]
    ps = session.prepare(
        """
        INSERT INTO usuarios_sistema (
            username, password_hash, rol, nombre, email,
            activo, fecha_creacion, ultimo_acceso
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    insert_many(session, ps, ((username, hash_password(password), rol, nombre, email, True, datetime.utcnow(), None) for username, password, rol, nombre, email in users), "usuarios_sistema")


def validate_counts(session) -> None:
    logger.info("Validando conteos principales...")
    tables = [
        "infraestructuras",
        "contratos",
        "medidores",
        "gateways",
        "tarifas",
        "modelos_medidor",
        "facturas",
        "resumen_dashboard_alcaldia",
        "resumen_dashboard_gerencia",
        "resumen_dashboard_contabilidad",
    ]
    for table in tables:
        try:
            row = session.execute(f"SELECT COUNT(*) FROM {table}").one()
            logger.info(f"{table}: {row.count:,}")
        except Exception as e:
            logger.warning(f"No se pudo contar {table}: {e}")


def main() -> None:
    logger.info("Iniciando seeder SEMAPA actualizado...")
    excel_path = find_file(EXCEL_PATH, ["recursos_practica_5.xlsx", "Recursos Practica 5.xlsx", "03 Practica 5 Recursos.xlsx"])
    infra_path = find_file(INFRA_CSV, ["infraestructuras_cochabamba.csv", "03 Practica 5 Recursos infraestructuras_cochabamba.csv"])
    contratos_path = find_file(CONTRATOS_CSV, ["contratos_agua.csv", "03 Practica 5 Recursos contratos_agua.csv"])
    medidores_path = find_file(MEDIDORES_CSV, ["medidores_iot.csv", "03 Practica 5 Recursos medidores_iot.csv"])

    wb = load_workbook(excel_path)
    _distritos, zonas = load_distritos_zonas(wb)
    _zones_by_key, zones_by_name, zones_list = build_zone_indexes(zonas)

    infra_rows = normalize_infra_rows(open_csv_dict(infra_path), zones_by_name, zones_list)
    contrato_rows = normalize_contrato_rows(open_csv_dict(contratos_path))
    infra_by_catastro = {i.numero_catastro: i for i in infra_rows}
    contratos_by_medidor = {c.medidor_iot: c for c in contrato_rows if c.medidor_iot}
    medidor_rows = normalize_medidor_rows(open_csv_dict(medidores_path), contratos_by_medidor, infra_by_catastro, zones_list)

    cluster, session = connect()
    try:
        if SEED_RESET:
            truncate_tables(session)
        seed_catalogos(session, wb)
        seed_personas(session, infra_rows, contrato_rows)
        seed_infraestructuras(session, infra_rows)
        seed_contratos(session, contrato_rows)
        seed_medidores(session, medidor_rows)
        seed_cobertura(session, medidor_rows)
        seed_facturas_y_resumenes(session, medidor_rows, contrato_rows, zonas, wb)
        seed_usuarios(session)
        validate_counts(session)
        logger.success("Seeder SEMAPA finalizado correctamente.")
    finally:
        session.shutdown()
        cluster.shutdown()


if __name__ == "__main__":
    main()
