"""Excel -> catálogos y plantillas para el seeder SEMAPA.

Compatible con la versión nueva del archivo:
    03 Practica 5 Recursos.xlsx

Hojas soportadas:
- Distritos: distribución territorial y cuotas por tarifa.
- Infraestructura: plantillas catastrales/direcciones/uso de suelo.
- Catastro: referencia del formato de número catastral.
- Contratos: plantillas de contratos, estados y subcategorías.
- Medidores: plantillas de MAC, estado y tipo de medidor.
- Lecturas: plantillas de lectura anterior/actual, radiobase y fecha de pago.
- Tarifario, ErroresIOT, ModeloMedidores, UnidadesEducativas.

Reglas importantes:
- No leer la hoja Distritos por posiciones rígidas antiguas. El Excel nuevo tiene
  18 columnas y las tarifas empiezan en R1..S.
- La clave territorial correcta es (distrito_id, zona_id). zona_id solo se repite.
- Las coordenadas oficiales de demo vienen de geo_reference.py, no de las muestras
  catastrales, para evitar puntos fuera de Cercado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl
from loguru import logger

from geo_reference import gateway_safe_point, zone_center


SUB_ALCALDIAS: list[tuple[int, str]] = [
    (1, "TUNARI"),
    (2, "MOLLE"),
    (3, "ALEJO CALATAYUD"),
    (4, "VALLE HERMOSO"),
    (5, "ITOCTA"),
    (6, "ADELA ZAMUDIO"),
]
SUB_ALCALDIA_ID = {n.upper(): i for i, n in SUB_ALCALDIAS}

SUB_ALCALDIA_BY_DISTRITO: dict[int, int] = {
    1: 1, 2: 1, 13: 1,
    3: 2, 4: 2,
    5: 3, 8: 3,
    6: 4, 7: 4, 14: 4,
    9: 5, 15: 5,
    10: 6, 11: 6, 12: 6,
}

BASE_GATEWAYS: dict[str, tuple[int, float, float]] = {
    "LoRaWan-Teleferico": (1, -17.389222, -66.141722),
    "LoRaWan-ParqueVial": (9, -17.381000, -66.153361),
    "LoRaWan-ParqueLincon": (17, -17.369861, -66.176389),
    "LoRaWan-Petrolera": (25, -17.444083, -66.140694),
}
GATEWAY_NAME_TO_ID = {name: start for name, (start, _lat, _lon) in BASE_GATEWAYS.items()}
TARIFA_HEADERS = ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def norm_key(value: Any) -> str:
    return clean_text(value).upper().replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")


def _as_int(x: Any) -> int | None:
    if x is None or x == "":
        return None
    try:
        return int(float(str(x).replace(",", ".")))
    except (TypeError, ValueError):
        return None


def _as_decimal(x: Any) -> Decimal:
    if x is None or x == "":
        return Decimal("0")
    return Decimal(str(x).replace(",", "."))


def _parse_date(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = clean_text(value)
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%d/%m/%y", "%d/%m/%Y", "%m/%d/%y %H:%M", "%d/%m/%y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def gateway_id_from_name(raw_name: str | None) -> int:
    text = clean_text(raw_name)
    for name, gid in GATEWAY_NAME_TO_ID.items():
        if name.upper() in text.upper():
            return gid
    return 1


def gateway_pool_for(gateway_id: int) -> list[int]:
    gid = int(gateway_id or 1)
    if 1 <= gid <= 8:
        start = 1
    elif 9 <= gid <= 16:
        start = 9
    elif 17 <= gid <= 24:
        start = 17
    elif 25 <= gid <= 32:
        start = 25
    else:
        start = 1
    return list(range(start, start + 8))


@dataclass
class Distrito:
    distrito_id: int
    sub_alcaldia_id: int
    nombre: str
    habitantes: int = 0


@dataclass
class Zona:
    distrito_id: int
    zona_id: int
    nombre: str
    gateway_id: int
    habitantes: int
    counts: dict[str, int] = field(default_factory=dict)
    centro_lat: float = -17.39
    centro_lon: float = -66.15

    @property
    def total_medidores(self) -> int:
        return sum(int(v or 0) for v in self.counts.values())


@dataclass
class ModeloMedidor:
    modelo_id: int
    marca: str
    modelo: str
    conectividad: str
    aplicacion: str


@dataclass
class TarifaCat:
    categoria: str
    alias: str
    fijo_m3: Decimal
    usd_mes: Decimal
    r_13_25: Decimal
    r_26_50: Decimal
    r_51_75: Decimal
    r_76_100: Decimal
    r_101_150: Decimal
    r_mas_151: Decimal
    descripcion: str


@dataclass
class TipoInfra:
    tipo_id: int
    descripcion: str


@dataclass
class UnidadEducativa:
    codigo: str
    nombre: str
    distrito_txt: str
    zona_txt: str
    direccion: str
    educacion: str


@dataclass
class InfraestructuraTemplate:
    numero_catastro: str
    propietario: str
    ci: str
    direccion: str
    zona: str
    distrito_id: int | None
    manzano: int | None
    lote: int | None
    superficie_terreno: int | None
    area_construida: int | None
    uso_suelo: str
    matricula_ddrr: str
    valor_catastral: Decimal
    impuesto_anual: Decimal


@dataclass
class ContratoTemplate:
    numero_catastro: str
    titular: str
    ci_titular: str
    categoria: str
    subcategoria: str
    medidor_iot: str
    fecha_contrato: datetime | None
    estado_contrato: str
    diametro_conexion: str
    tipo_servicio: str


@dataclass
class MedidorTemplate:
    medidor_iot: str
    fecha_instalacion: datetime | None
    fecha_desinstalacion: datetime | None
    estado: str
    tipo_medidor_id: int | None


@dataclass
class LecturaTemplate:
    medidor_iot: str
    lectura_anterior: int
    lectura_actual: int
    fecha_hora: datetime | None
    radiobase: int | None
    fecha_pago: datetime | None


def load_workbook(path: str | Path) -> openpyxl.Workbook:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Excel no encontrado: {p}")
    logger.info(f"Cargando Excel: {p}")
    return openpyxl.load_workbook(p, data_only=True, read_only=False)


def _sheet(wb: openpyxl.Workbook, *names: str):
    lower = {s.lower(): s for s in wb.sheetnames}
    for name in names:
        found = lower.get(name.lower())
        if found:
            return wb[found]
    raise KeyError(f"No se encontró ninguna hoja: {names}. Disponibles: {wb.sheetnames}")


def load_distritos_zonas(wb: openpyxl.Workbook) -> tuple[list[Distrito], list[Zona]]:
    ws = _sheet(wb, "Distritos")
    # Buscar fila de encabezados donde estén R1..S y Total. En el Excel nuevo es fila 2.
    header_row = 2
    headers = [clean_text(c.value) for c in ws[header_row]]
    tariff_cols: dict[str, int] = {}
    for idx, h in enumerate(headers):
        hu = h.upper()
        if hu in TARIFA_HEADERS:
            tariff_cols[hu] = idx
    if set(TARIFA_HEADERS) - set(tariff_cols):
        raise ValueError(f"La hoja Distritos no tiene todas las tarifas {TARIFA_HEADERS}. Headers={headers}")

    # Posiciones estables del Excel nuevo.
    COL_SUB = 0
    COL_DIST = 1
    COL_ZONA = 2
    COL_NOMBRE_ZONA = 3
    COL_GATEWAY = 4
    COL_ZONE_POP = 6     # población estimada de la zona (suma ≈ población beneficiaria)
    COL_SUB_HAB = 7      # total por subalcaldía, solo primera fila de cada subalcaldía
    COL_TOTAL = next((i for i, h in enumerate(headers) if h.upper() == "TOTAL"), 17)

    distritos: dict[int, Distrito] = {}
    zonas: list[Zona] = []
    cur_sub = ""
    cur_dist: int | None = None
    cur_habitantes = 0
    habitantes_por_distrito: dict[int, int] = {}

    for row_idx, row in enumerate(ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1):
        if not row or all(v is None for v in row):
            continue
        if row[COL_SUB] is not None:
            cur_sub = clean_text(row[COL_SUB]).upper()
        if row[COL_DIST] is not None:
            cur_dist = _as_int(row[COL_DIST])
            cur_habitantes = _as_int(row[COL_SUB_HAB] if len(row) > COL_SUB_HAB else None) or cur_habitantes
            if cur_dist is not None and cur_dist not in distritos:
                distritos[cur_dist] = Distrito(
                    distrito_id=cur_dist,
                    sub_alcaldia_id=SUB_ALCALDIA_BY_DISTRITO.get(cur_dist, SUB_ALCALDIA_ID.get(cur_sub.replace("\n", " "), 1)),
                    nombre=f"DISTRITO {cur_dist}",
                    habitantes=cur_habitantes,
                )
        elif cur_dist is not None and len(row) > COL_SUB_HAB and row[COL_SUB_HAB] is not None and distritos[cur_dist].habitantes == 0:
            distritos[cur_dist].habitantes = _as_int(row[COL_SUB_HAB]) or 0

        zona_id = _as_int(row[COL_ZONA] if len(row) > COL_ZONA else None)
        zona_nombre = clean_text(row[COL_NOMBRE_ZONA] if len(row) > COL_NOMBRE_ZONA else None)
        if cur_dist is None or zona_id is None or not zona_nombre:
            continue

        counts = {cat: _as_int(row[col] if col < len(row) else None) or 0 for cat, col in tariff_cols.items()}
        total_col = _as_int(row[COL_TOTAL] if COL_TOTAL < len(row) else None) or 0
        zona_habitantes = _as_int(row[COL_ZONE_POP] if len(row) > COL_ZONE_POP else None) or 0
        habitantes_por_distrito[cur_dist] = habitantes_por_distrito.get(cur_dist, 0) + zona_habitantes
        if not any(counts.values()) and total_col == 0:
            continue
        if total_col and sum(counts.values()) != total_col:
            logger.warning(
                f"Fila {row_idx}: suma tarifas={sum(counts.values())} != Total={total_col} "
                f"en D{cur_dist}/Z{zona_id} {zona_nombre}"
            )

        gw_id = gateway_id_from_name(row[COL_GATEWAY] if len(row) > COL_GATEWAY else None)
        centro = zone_center(cur_dist, zona_id)
        zonas.append(
            Zona(
                distrito_id=cur_dist,
                zona_id=zona_id,
                nombre=zona_nombre,
                gateway_id=gw_id,
                habitantes=zona_habitantes,
                counts={cat: counts.get(cat, 0) for cat in TARIFA_HEADERS},
                centro_lat=centro[0],
                centro_lon=centro[1],
            )
        )

    # Habitantes del distrito = suma de habitantes de sus zonas. Si una zona no trae
    # población, se reparte proporcionalmente desde el total de subalcaldía disponible.
    for dist in distritos.values():
        zonas_d = [z for z in zonas if z.distrito_id == dist.distrito_id]
        suma_zonas = sum(z.habitantes for z in zonas_d)
        if suma_zonas > 0:
            dist.habitantes = suma_zonas
        elif dist.habitantes and zonas_d:
            total = sum(z.total_medidores for z in zonas_d) or 1
            for z in zonas_d:
                z.habitantes = int(dist.habitantes * z.total_medidores / total)

    total_base = sum(z.total_medidores for z in zonas)
    logger.info(f"Distritos cargados: {len(distritos)} | Zonas: {len(zonas)} | Total base={total_base:,}")
    if total_base != 100000:
        logger.warning(f"La hoja Distritos no suma 100.000; suma={total_base:,}")
    return sorted(distritos.values(), key=lambda d: d.distrito_id), zonas


def load_tarifas(wb: openpyxl.Workbook) -> list[TarifaCat]:
    ws = _sheet(wb, "Tarifario")
    out: list[TarifaCat] = []
    cur_alias = ""
    for row in ws.iter_rows(min_row=3, values_only=True):
        if not row or all(v is None for v in row):
            continue
        alias_txt, cat, fijo, usd, r1, r2, r3, r4, r5, r6, desc = (list(row) + [None] * 11)[:11]
        if alias_txt:
            cur_alias = clean_text(alias_txt)
        cat_txt = clean_text(cat).upper()
        if not cat_txt or cat_txt not in TARIFA_HEADERS:
            continue
        out.append(TarifaCat(cat_txt, cur_alias, _as_decimal(fijo), _as_decimal(usd), _as_decimal(r1), _as_decimal(r2), _as_decimal(r3), _as_decimal(r4), _as_decimal(r5), _as_decimal(r6), clean_text(desc)))
    found = {t.categoria for t in out}
    missing = set(TARIFA_HEADERS) - found
    if missing:
        raise ValueError(f"Faltan tarifas en Tarifario: {sorted(missing)}")
    logger.info(f"Tarifas: {len(out)} categorías")
    return out


def load_modelos(wb: openpyxl.Workbook) -> list[ModeloMedidor]:
    ws = _sheet(wb, "ModeloMedidores")
    out: list[ModeloMedidor] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        mid = _as_int(row[0] if row else None)
        if mid is None:
            continue
        out.append(ModeloMedidor(mid, clean_text(row[1]), clean_text(row[2]), clean_text(row[3]), clean_text(row[4])))
    logger.info(f"Modelos medidor: {len(out)}")
    return out


def load_errores(wb: openpyxl.Workbook) -> list[tuple[int, str]]:
    ws = _sheet(wb, "ErroresIOT")
    out: list[tuple[int, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        code = _as_int(row[0] if row else None)
        if code is None:
            continue
        out.append((code, clean_text(row[1])))
    logger.info(f"Errores IoT: {len(out)}")
    return out


def load_tipos_infra(wb: openpyxl.Workbook) -> list[TipoInfra]:
    # El XLSX nuevo ya no usa la hoja antigua Infraestructuras como catálogo;
    # trae Infraestructura como ejemplos. Extraemos usos de suelo y completamos
    # con tipos que el enunciado pide.
    base = [
        "Educativo", "Salud", "Asilo / Convento / Iglesia", "Beneficencia",
        "Área verde / Parque", "Centro comunal / Cultural", "Infraestructura pública / Hidrante",
        "Terreno baldío", "Casa abandonada", "Edificio", "Condominio", "Residencial",
        "Comercial", "Comercial Especial", "Industrial", "Mixto",
    ]
    usos: list[str] = []
    try:
        ws = _sheet(wb, "Infraestructura")
        headers = [norm_key(c.value) for c in ws[1]]
        col_uso = headers.index("USO_SUELO") if "USO_SUELO" in headers else None
        if col_uso is not None:
            for row in ws.iter_rows(min_row=2, values_only=True):
                val = clean_text(row[col_uso] if col_uso < len(row) else None)
                if val and val not in usos:
                    usos.append(val)
    except Exception:
        pass
    merged = []
    for v in usos + base:
        if v and v not in merged:
            merged.append(v)
    out = [TipoInfra(i + 1, desc) for i, desc in enumerate(merged)]
    logger.info(f"Tipos infraestructura: {len(out)}")
    return out


def load_unidades_educativas(wb: openpyxl.Workbook) -> list[UnidadEducativa]:
    ws = _sheet(wb, "UnidadesEducativas")
    out: list[UnidadEducativa] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[1] is None:
            continue
        out.append(UnidadEducativa(clean_text(row[1]), clean_text(row[2]), clean_text(row[0]), clean_text(row[7]), clean_text(row[8]), clean_text(row[3])))
    logger.info(f"Unidades educativas: {len(out)}")
    return out


def load_infraestructura_templates(wb: openpyxl.Workbook) -> list[InfraestructuraTemplate]:
    ws = _sheet(wb, "Infraestructura")
    out: list[InfraestructuraTemplate] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        out.append(InfraestructuraTemplate(
            numero_catastro=clean_text(row[0]), propietario=clean_text(row[1]), ci=clean_text(row[2]),
            direccion=clean_text(row[3]), zona=clean_text(row[4]), distrito_id=_as_int(row[5]),
            manzano=_as_int(row[6]), lote=_as_int(row[7]), superficie_terreno=_as_int(row[8]),
            area_construida=_as_int(row[9]), uso_suelo=clean_text(row[10]), matricula_ddrr=clean_text(row[11]),
            valor_catastral=_as_decimal(row[12]), impuesto_anual=_as_decimal(row[13]),
        ))
    logger.info(f"Plantillas infraestructura/catastro: {len(out)}")
    return out


def load_contratos_templates(wb: openpyxl.Workbook) -> list[ContratoTemplate]:
    ws = _sheet(wb, "Contratos")
    out: list[ContratoTemplate] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        out.append(ContratoTemplate(
            numero_catastro=clean_text(row[0]), titular=clean_text(row[1]), ci_titular=clean_text(row[2]),
            categoria=clean_text(row[3]), subcategoria=clean_text(row[4]).upper(), medidor_iot=clean_text(row[5]),
            fecha_contrato=_parse_date(row[6]), estado_contrato=clean_text(row[7]).upper(),
            diametro_conexion=clean_text(row[8]), tipo_servicio=clean_text(row[9]),
        ))
    logger.info(f"Plantillas contratos: {len(out)}")
    return out


def load_medidores_templates(wb: openpyxl.Workbook) -> list[MedidorTemplate]:
    ws = _sheet(wb, "Medidores")
    out: list[MedidorTemplate] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        out.append(MedidorTemplate(clean_text(row[0]), _parse_date(row[1]), _parse_date(row[2]), clean_text(row[3]), _as_int(row[4])))
    logger.info(f"Plantillas medidores: {len(out)}")
    return out


def load_lecturas_templates(wb: openpyxl.Workbook) -> list[LecturaTemplate]:
    ws = _sheet(wb, "Lecturas")
    out: list[LecturaTemplate] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:
            continue
        out.append(LecturaTemplate(clean_text(row[0]), _as_int(row[1]) or 0, _as_int(row[2]) or 0, _parse_date(row[3]), _as_int(row[4]), _parse_date(row[5])))
    logger.info(f"Plantillas lecturas: {len(out)}")
    return out


def make_catastro_number(distrito_id: int, zona_id: int, manzano: int, lote: int, subdivision: int = 0) -> str:
    return f"{int(distrito_id):02d}-{int(zona_id):02d}-{int(manzano) % 1000:03d}-{int(lote) % 10000:04d}-{int(subdivision) % 1000:03d}"


def gateways() -> list[tuple[int, str, float, float]]:
    out: list[tuple[int, str, float, float]] = []
    for base_name, (start_id, _base_lat, _base_lon) in BASE_GATEWAYS.items():
        for offset in range(8):
            gid = start_id + offset
            lat, lon = gateway_safe_point(gid)
            out.append((gid, f"{base_name}-GW{offset + 1:02d}", lat, lon))
    return out
