"""Excel → estructuras tipadas para el seeder.

Lee Recursos_Practica_5.xlsx (montado vía volumen Docker en /recursos/recursos.xlsx)
y devuelve catálogos limpios: sub_alcaldias, distritos, zonas, gateways, modelos,
tarifas, errores, tipos de infraestructura, unidades educativas, infraestructuras
públicas.

Diseño:
- Lectura una sola vez con openpyxl (data_only=True para resolver fórmulas).
- Forward-fill manual de columnas jerárquicas (sub_alcaldia/distrito).
- Coordenadas DMS → decimales para gateways.
- Datos canonicalizados a int/Decimal/str (sin NaN sueltos).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterable

import openpyxl
from loguru import logger
from geo_reference import gateway_safe_point, zone_center


# ----- Sub-alcaldías (fijas, derivadas del Excel + enunciado) -----
SUB_ALCALDIAS: list[tuple[int, str]] = [
    (1, "TUNARI"),
    (2, "MOLLE"),
    (3, "ALEJO CALATAYUD"),
    (4, "VALLE HERMOSO"),
    (5, "ITOCTA"),
    (6, "ADELA ZAMUDIO"),
]
SUB_ALCALDIA_ID = {n.upper(): i for i, n in SUB_ALCALDIAS}

# Fallback territorial para evitar errores por celdas combinadas del Excel.
SUB_ALCALDIA_BY_DISTRITO: dict[int, int] = {
    1: 1, 2: 1, 13: 1,
    3: 2, 4: 2,
    5: 3, 8: 3,
    6: 4, 7: 4, 14: 4,
    9: 5, 15: 5,
    10: 6, 11: 6, 12: 6,
}

# PDF actualizado: la red LoRaWAN trabaja con 14 radiobases.
# Se mantienen alias de los nombres anteriores para compatibilidad con el Excel.
BASE_GATEWAYS: dict[str, int] = {
    "LoRaWan-Teleferico": 1,
    "LoRaWan-ParqueVial": 4,
    "LoRaWan-ParqueLincon": 8,
    "LoRaWan-Petrolera": 12,
}

GATEWAY_NAME_TO_ID = {name: gid for name, gid in BASE_GATEWAYS.items()}


def gateway_id_from_name(raw_name: str | None, distrito_id: int | None = None, zona_id: int | None = None) -> int:
    """Devuelve radiobase 1..14.

    El PDF actualizado cambió de 32 a 14 radiobases. Si el Excel trae nombres
    antiguos, se mapean a una radiobase cercana. Si no hay nombre, se reparte
    de forma determinística por distrito/zona para no dejar todo en RB01.
    """
    text = (raw_name or "").strip()
    for name, gid in GATEWAY_NAME_TO_ID.items():
        if name in text:
            return gid
    try:
        d = int(distrito_id or 1)
        z = int(zona_id or 1)
        return ((d * 37 + z * 11) % 14) + 1
    except Exception:
        return 1


def gateway_pool_for(gateway_id: int) -> list[int]:
    """La versión actual usa 14 radiobases físicas, sin expansión a 32."""
    try:
        gid = int(gateway_id)
    except Exception:
        gid = 1
    if not 1 <= gid <= 14:
        gid = ((gid - 1) % 14) + 1
    return [gid]


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
    habitantes: int  # cuota proporcional
    counts: dict[str, int] = field(default_factory=dict)  # categoría → cantidad
    centro_lat: float = -17.39
    centro_lon: float = -66.15

    @property
    def total_medidores(self) -> int:
        return sum(self.counts.values())


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


# Coordenadas aproximadas (centroide) por distrito de Cochabamba urbano.

# Centros corregidos por clave compuesta distrito_id + zona_id.
# Importante: zona_id solo no alcanza porque hay IDs repetidos entre distritos.
ZONE_CENTERS_BY_KEY: dict[tuple[int, int], tuple[float, float]] = {
    (1, 24): (-17.3826, -66.1320), (1, 25): (-17.3862, -66.1195), (1, 26): (-17.3920, -66.1085),
    (2, 1): (-17.3890, -66.1780), (2, 3): (-17.3868, -66.1680), (2, 22): (-17.3730, -66.1805),
    (2, 23): (-17.3770, -66.1690), (2, 24): (-17.3825, -66.1608), (2, 27): (-17.3845, -66.1515),
    (13, 35): (-17.3365, -66.1460),
    (3, 2): (-17.3970, -66.1840), (3, 21): (-17.3910, -66.1940), (3, 37): (-17.4050, -66.1840),
    (4, 10): (-17.4160, -66.1800), (4, 27): (-17.4080, -66.1900), (4, 28): (-17.4180, -66.1960),
    (5, 14): (-17.4330, -66.1700), (5, 15): (-17.4270, -66.1580), (5, 17): (-17.4370, -66.1520),
    (5, 18): (-17.4340, -66.0990), (5, 20): (-17.4400, -66.1070), (8, 34): (-17.4480, -66.1110),
    (8, 35): (-17.4580, -66.1020), (8, 36): (-17.4660, -66.0940),
    (6, 16): (-17.4130, -66.1450), (6, 32): (-17.4160, -66.1510),
    (7, 19): (-17.4220, -66.1330), (7, 20): (-17.4310, -66.1300), (14, 34): (-17.4300, -66.1200),
    (9, 29): (-17.4640, -66.1910), (9, 30): (-17.4720, -66.2050), (9, 31): (-17.4600, -66.2190),
    (9, 35): (-17.4800, -66.1970), (9, 36): (-17.4640, -66.2290),
    (15, 32): (-17.4600, -66.1390), (15, 33): (-17.4740, -66.1410), (15, 34): (-17.4690, -66.1260),
    (15, 35): (-17.4850, -66.1300), (15, 36): (-17.4930, -66.1510), (15, 37): (-17.4980, -66.1670), (15, 38): (-17.5050, -66.1850),
    (10, 7): (-17.3980, -66.1590), (10, 8): (-17.3980, -66.1490), (10, 11): (-17.4100, -66.1610),
    (10, 12): (-17.4100, -66.1490), (11, 9): (-17.4080, -66.1380), (11, 13): (-17.4140, -66.1440),
    (12, 2): (-17.3930, -66.1730), (12, 3): (-17.3890, -66.1670), (12, 4): (-17.3870, -66.1590),
    (12, 5): (-17.3990, -66.1590), (12, 6): (-17.4030, -66.1690),
}

DISTRITO_CENTROIDES: dict[int, tuple[float, float]] = {
    1: (-17.378, -66.150),
    2: (-17.395, -66.155),
    3: (-17.401, -66.160),
    4: (-17.405, -66.140),
    5: (-17.412, -66.142),
    6: (-17.418, -66.158),
    7: (-17.423, -66.165),
    8: (-17.430, -66.155),
    9: (-17.438, -66.148),
    10: (-17.445, -66.130),
    11: (-17.452, -66.140),
    12: (-17.395, -66.180),
    13: (-17.410, -66.190),
    14: (-17.420, -66.200),
    15: (-17.460, -66.170),
}


def _parse_dms(dms: str) -> float | None:
    m = re.match(r"(\d+)°(\d+)'(\d+\.?\d*)\"([NSEW])", dms.strip())
    if not m:
        return None
    deg, mn, sec, hemi = m.groups()
    val = int(deg) + int(mn) / 60 + float(sec) / 3600
    if hemi in ("S", "W"):
        val = -val
    return val


def _as_int(x) -> int | None:
    if x is None:
        return None
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return None


def load_workbook(path: str | Path) -> openpyxl.Workbook:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Excel no encontrado: {p}")
    logger.info(f"Cargando Excel: {p}")
    return openpyxl.load_workbook(p, data_only=True, read_only=False)


def load_distritos_zonas(wb: openpyxl.Workbook) -> tuple[list[Distrito], list[Zona]]:
    """Lee la hoja Distritos del Excel nuevo sin depender de posiciones fijas.

    El Excel actualizado agregó columnas intermedias. Por eso se detectan
    encabezados por nombre: R1, R2, R3, R4, C, CE, I, P, S, Total, HABITANTES.
    """
    ws = wb["Distritos"]
    headers = [str(c.value or "").strip().upper() for c in ws[2]]

    def col(name: str, default: int | None = None) -> int:
        name_u = name.upper()
        for idx, h in enumerate(headers):
            if h == name_u or name_u in h:
                return idx
        if default is not None:
            return default
        raise KeyError(f"No se encontró columna {name!r} en Distritos: {headers}")

    idx_sub = 0
    idx_dist = 1
    idx_zona = col("SUB-DISTRITO", 2)
    idx_nombre = col("ZONA", 3)
    idx_hab = col("HABITANTES", 7)
    idx_gateway = 4  # sin encabezado explícito en la versión actual
    cat_cols = {cat: headers.index(cat) for cat in ["R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"]}

    distritos: dict[int, Distrito] = {}
    zonas: list[Zona] = []
    cur_sub: str | None = None
    cur_dist: int | None = None

    for row_idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if row is None or all(c is None for c in row):
            continue
        if row[idx_sub]:
            cur_sub = str(row[idx_sub]).strip().upper()
        if row[idx_dist] is not None:
            cur_dist = _as_int(row[idx_dist])
            if cur_dist is not None and cur_dist not in distritos:
                distritos[cur_dist] = Distrito(
                    distrito_id=cur_dist,
                    sub_alcaldia_id=SUB_ALCALDIA_BY_DISTRITO.get(cur_dist, SUB_ALCALDIA_ID.get(cur_sub or "", 1)),
                    nombre=f"DISTRITO {cur_dist}",
                    habitantes=_as_int(row[idx_hab]) or 0,
                )
        if cur_dist is not None and row[idx_hab] and cur_dist in distritos and distritos[cur_dist].habitantes == 0:
            distritos[cur_dist].habitantes = _as_int(row[idx_hab]) or 0

        zid = _as_int(row[idx_zona])
        zona_nom = row[idx_nombre]
        if zid is None or not zona_nom or cur_dist is None:
            continue
        counts = {cat: _as_int(row[i]) or 0 for cat, i in cat_cols.items()}
        gw_name = row[idx_gateway] if idx_gateway < len(row) else None
        gw_id = gateway_id_from_name(str(gw_name).strip() if gw_name else "", cur_dist, zid)
        centro = zone_center(cur_dist, zid)
        zonas.append(Zona(
            distrito_id=cur_dist,
            zona_id=zid,
            nombre=str(zona_nom).strip(),
            gateway_id=gw_id,
            habitantes=0,
            counts=counts,
            centro_lat=centro[0],
            centro_lon=centro[1],
        ))

    for dist in distritos.values():
        zonas_d = [z for z in zonas if z.distrito_id == dist.distrito_id]
        total = sum(z.total_medidores for z in zonas_d) or 1
        for z in zonas_d:
            z.habitantes = int(dist.habitantes * z.total_medidores / total)

    logger.info(f"Distritos cargados: {len(distritos)} | Zonas: {len(zonas)} | Total distribución={sum(z.total_medidores for z in zonas):,}")
    return list(distritos.values()), zonas


def load_tarifas(wb: openpyxl.Workbook) -> list[TarifaCat]:
    ws = wb["Tarifario"]
    rows = list(ws.iter_rows(min_row=3, max_row=12, values_only=True))
    out: list[TarifaCat] = []
    cur_alias = None
    for row in rows:
        if row is None or all(c is None for c in row):
            continue
        alias_txt, cat, fijo, usd, r1, r2, r3, r4, r5, r6, desc = row[:11]
        if alias_txt:
            cur_alias = str(alias_txt).strip()
        if not cat:
            continue
        out.append(
            TarifaCat(
                categoria=str(cat).strip().upper(),
                alias=cur_alias or "",
                fijo_m3=Decimal(str(fijo or 0)),
                usd_mes=Decimal(str(usd or 0)),
                r_13_25=Decimal(str(r1 or 0)),
                r_26_50=Decimal(str(r2 or 0)),
                r_51_75=Decimal(str(r3 or 0)),
                r_76_100=Decimal(str(r4 or 0)),
                r_101_150=Decimal(str(r5 or 0)),
                r_mas_151=Decimal(str(r6 or 0)),
                descripcion=str(desc or "").strip(),
            )
        )
    # Garantizar las 9 categorías
    needed = {"R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"}
    found = {t.categoria for t in out}
    missing = needed - found
    if missing:
        logger.warning(f"Tarifas faltantes en Excel: {missing}. Se añadirán fallback.")
        fallbacks = {
            "S": TarifaCat("S", "Social", Decimal("8"), Decimal("0.67"), Decimal("0.5"),
                           Decimal("0.6"), Decimal("0.7"), Decimal("0.8"), Decimal("0.9"),
                           Decimal("1.0"), "Tarifa social, predios estatales con fines sociales"),
        }
        for m in missing:
            if m in fallbacks:
                out.append(fallbacks[m])
    logger.info(f"Tarifas: {len(out)} categorías")
    return out


def load_modelos(wb: openpyxl.Workbook) -> list[ModeloMedidor]:
    ws = wb["ModeloMedidores"]
    out: list[ModeloMedidor] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        tid, marca, modelo, conect, app, _ = row[:6]
        mid = _as_int(tid)
        if mid is None:
            continue
        out.append(
            ModeloMedidor(
                modelo_id=mid,
                marca=str(marca or "").strip(),
                modelo=str(modelo or "").strip(),
                conectividad=str(conect or "").strip(),
                aplicacion=str(app or "").strip(),
            )
        )
    logger.info(f"Modelos medidor: {len(out)}")
    return out


def load_errores(wb: openpyxl.Workbook) -> list[tuple[int, str]]:
    ws = wb["ErroresIOT"]
    out: list[tuple[int, str]] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        code = _as_int(row[0])
        if code is None:
            continue
        out.append((code, str(row[1] or "").strip()))
    logger.info(f"Errores IoT: {len(out)}")
    return out


def load_tipos_infra(wb: openpyxl.Workbook) -> list[TipoInfra]:
    """Carga tipos de infraestructura.

    El Excel actualizado reemplazó la hoja de tipos por una hoja de
    infraestructura catastral masiva. Por compatibilidad se mantienen los 12
    tipos usados por el proyecto y la práctica.
    """
    if "Infraestructuras" in wb.sheetnames:
        ws = wb["Infraestructuras"]
        out: list[TipoInfra] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row:
                continue
            tid = _as_int(row[0])
            if tid is None:
                continue
            out.append(TipoInfra(tipo_id=tid, descripcion=str(row[1] or "").strip()))
        if out:
            logger.info(f"Tipos infraestructura: {len(out)}")
            return out
    out = [
        TipoInfra(1, "Unidades Educativas"),
        TipoInfra(2, "Hospitales públicos / centros de salud"),
        TipoInfra(3, "Asilos, conventos, iglesias"),
        TipoInfra(4, "Centros de beneficencia o protección estatal"),
        TipoInfra(5, "Parques, jardines, áreas verdes"),
        TipoInfra(6, "Salones comunales, centros culturales"),
        TipoInfra(7, "Policía / Ejército / entidad pública"),
        TipoInfra(8, "Terrenos baldíos"),
        TipoInfra(9, "Viviendas habitadas"),
        TipoInfra(10, "Viviendas no habitadas"),
        TipoInfra(11, "Edificios"),
        TipoInfra(12, "Condominios / uso mixto"),
    ]
    logger.info(f"Tipos infraestructura fallback: {len(out)}")
    return out


def load_unidades_educativas(wb: openpyxl.Workbook) -> list[UnidadEducativa]:
    ws = wb["UnidadesEducativas"]
    out: list[UnidadEducativa] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[1] is None:
            continue
        out.append(
            UnidadEducativa(
                codigo=str(row[1]),
                nombre=str(row[2] or "").strip(),
                distrito_txt=str(row[0] or "").strip(),
                zona_txt=str(row[7] or "").strip(),
                direccion=str(row[8] or "").strip(),
                educacion=str(row[3] or "").strip(),
            )
        )
    logger.info(f"Unidades educativas: {len(out)}")
    return out


def gateways() -> list[tuple[int, str, float, float]]:
    """Devuelve las 14 radiobases LoRaWAN del PDF actualizado."""
    out: list[tuple[int, str, float, float]] = []
    for gid in range(1, 15):
        lat, lon = gateway_safe_point(gid)
        out.append((gid, f"LoRaWAN-RB{gid:02d}", lat, lon))
    return out
