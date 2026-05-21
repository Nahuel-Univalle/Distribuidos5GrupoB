"""Referencia geográfica SEMAPA – Práctica 5 / Municipio Cercado.

Fuente usada para la defensa:
- Presentación de la Práctica 5: árbol SubAlcaldía -> Distrito -> Subdistrito/Zona.
- El proyecto trabaja SOLO el municipio Cercado de Cochabamba.
- La clave territorial correcta es (distrito_id, zona_id). No usar zona_id solo,
  porque varios subdistritos/zona se repiten en distintos distritos.

Objetivo técnico:
- Generar y reparar coordenadas de infraestructuras, medidores y gateways sin
  salir del límite visible de Cercado.
- Evitar que aparezcan puntos en Tiquipaya, Colcapirhua, Quillacollo o Sacaba.
- Mantener los datos preparados para que luego el ingeniero/docente reemplace
  estos centroides por polígonos oficiales si entrega una capa más precisa.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ZonaTerritorial:
    sub_alcaldia: str
    distrito_id: int
    zona_id: int
    zona: str
    lat: float
    lon: float


# Caja estricta de seguridad visual. No pretende ser catastro oficial; evita que
# los datos se pinten fuera del municipio trabajado en la práctica.
# (lat_min, lat_max, lon_min, lon_max)
CERCADO_STRICT_BOUNDS = (-17.5120, -17.3180, -66.2380, -66.1080)

# Polígono conservador para máscara/fallback. Orden: (lat, lon).
CERCADO_RING: list[tuple[float, float]] = [
    (-17.3180, -66.1600),
    (-17.3360, -66.1250),
    (-17.3740, -66.1160),
    (-17.4050, -66.1150),
    (-17.4380, -66.1080),
    (-17.4660, -66.1160),
    (-17.4920, -66.1360),
    (-17.5060, -66.1900),
    (-17.4880, -66.2320),
    (-17.4500, -66.2320),
    (-17.4200, -66.2220),
    (-17.3880, -66.2140),
    (-17.3560, -66.1980),
    (-17.3180, -66.1600),
]

# Árbol territorial de la presentación de la práctica 5 + zona adicional del Excel
# para el Distrito 13. Los centroides son conservadores: quedan dentro del distrito
# visible para que la demo no pinte datos fuera de Cercado.
TERRITORIO_ZONAS: dict[tuple[int, int], ZonaTerritorial] = {
    # TUNARI
    (1, 24): ZonaTerritorial("TUNARI", 1, 24, "QUERU QUERU ALTO", -17.3845, -66.1315),
    (1, 25): ZonaTerritorial("TUNARI", 1, 25, "ARANJUEZ ALTO", -17.3860, -66.1230),
    (1, 26): ZonaTerritorial("TUNARI", 1, 26, "MESADILLA", -17.3900, -66.1280),
    (2, 1): ZonaTerritorial("TUNARI", 2, 1, "MAYORAZGO", -17.3815, -66.1780),
    (2, 3): ZonaTerritorial("TUNARI", 2, 3, "CALA CALA", -17.3790, -66.1690),
    (2, 22): ZonaTerritorial("TUNARI", 2, 22, "CONDEBAMBA", -17.3730, -66.1800),
    (2, 23): ZonaTerritorial("TUNARI", 2, 23, "TEMPORAL PAMPA", -17.3760, -66.1680),
    (2, 24): ZonaTerritorial("TUNARI", 2, 24, "QUERU QUERU ALTO", -17.3820, -66.1610),
    (13, 24): ZonaTerritorial("TUNARI", 13, 24, "LA TEMIBLE CARA CARA", -17.3380, -66.1460),

    # MOLLE
    (3, 2): ZonaTerritorial("MOLLE", 3, 2, "SARCO", -17.3955, -66.1860),
    (3, 6): ZonaTerritorial("MOLLE", 3, 6, "HIPODROMO", -17.3990, -66.1765),
    (3, 21): ZonaTerritorial("MOLLE", 3, 21, "SARCOBAMBA", -17.3910, -66.1940),
    (3, 27): ZonaTerritorial("MOLLE", 3, 27, "VILLA BUSCH", -17.3978, -66.2010),
    (3, 37): ZonaTerritorial("MOLLE", 3, 37, "CHIQUICOLLO", -17.4040, -66.1860),
    (4, 6): ZonaTerritorial("MOLLE", 4, 6, "HIPODROMO", -17.4075, -66.1765),
    (4, 10): ZonaTerritorial("MOLLE", 4, 10, "LA CHIMBA", -17.4160, -66.1800),
    (4, 27): ZonaTerritorial("MOLLE", 4, 27, "VILLA BUSCH", -17.4090, -66.1900),
    (4, 28): ZonaTerritorial("MOLLE", 4, 28, "COÑA COÑA", -17.4185, -66.1970),

    # ALEJO CALATAYUD
    (5, 12): ZonaTerritorial("ALEJO CALATAYUD", 5, 12, "SUDESTE", -17.4290, -66.1580),
    (5, 14): ZonaTerritorial("ALEJO CALATAYUD", 5, 14, "LA MAICA", -17.4360, -66.1760),
    (5, 15): ZonaTerritorial("ALEJO CALATAYUD", 5, 15, "JAIHUAYCO", -17.4265, -66.1605),
    (5, 16): ZonaTerritorial("ALEJO CALATAYUD", 5, 16, "ALALAY NORTE", -17.4215, -66.1510),
    (5, 17): ZonaTerritorial("ALEJO CALATAYUD", 5, 17, "LACMA", -17.4380, -66.1530),
    (8, 18): ZonaTerritorial("ALEJO CALATAYUD", 8, 18, "TICTI", -17.4420, -66.1160),
    (8, 20): ZonaTerritorial("ALEJO CALATAYUD", 8, 20, "VALLE HERMOSO", -17.4490, -66.1140),
    (8, 34): ZonaTerritorial("ALEJO CALATAYUD", 8, 34, "USPHA USPHA", -17.4470, -66.1210),

    # VALLE HERMOSO
    (6, 16): ZonaTerritorial("VALLE HERMOSO", 6, 16, "ALALAY NORTE", -17.4140, -66.1460),
    (7, 16): ZonaTerritorial("VALLE HERMOSO", 7, 16, "ALALAY NORTE", -17.4195, -66.1340),
    (7, 19): ZonaTerritorial("VALLE HERMOSO", 7, 19, "ALALAY SUD", -17.4250, -66.1305),
    (14, 19): ZonaTerritorial("VALLE HERMOSO", 14, 19, "ALALAY SUD", -17.4375, -66.1220),
    (14, 20): ZonaTerritorial("VALLE HERMOSO", 14, 20, "VALLE HERMOSO", -17.4450, -66.1185),

    # ITOCTA
    (9, 14): ZonaTerritorial("ITOCTA", 9, 14, "LA MAICA", -17.4480, -66.1940),
    (9, 28): ZonaTerritorial("ITOCTA", 9, 28, "COÑA COÑA", -17.4385, -66.2110),
    (9, 29): ZonaTerritorial("ITOCTA", 9, 29, "TAMBORADA PUKARITA", -17.4635, -66.1910),
    (9, 30): ZonaTerritorial("ITOCTA", 9, 30, "1° DE MAYO", -17.4720, -66.2075),
    (9, 31): ZonaTerritorial("ITOCTA", 9, 31, "PUKARA GRANDE NORTE", -17.4595, -66.2210),
    (9, 32): ZonaTerritorial("ITOCTA", 9, 32, "VALLE HERMOSO OESTE", -17.4560, -66.1720),
    (9, 35): ZonaTerritorial("ITOCTA", 9, 35, "PUKARA GRANDE SUR", -17.4810, -66.1980),
    (9, 36): ZonaTerritorial("ITOCTA", 9, 36, "PUKARA GRANDE OESTE", -17.4650, -66.2290),
    (15, 32): ZonaTerritorial("ITOCTA", 15, 32, "VALLE HERMOSO OESTE", -17.4610, -66.1430),
    (15, 33): ZonaTerritorial("ITOCTA", 15, 33, "KHARA KHARA ARRUMANI", -17.4740, -66.1390),
    (15, 35): ZonaTerritorial("ITOCTA", 15, 35, "PUKARA GRANDE SUR", -17.4820, -66.1340),

    # ADELA ZAMUDIO
    (10, 7): ZonaTerritorial("ADELA ZAMUDIO", 10, 7, "NOROESTE", -17.3980, -66.1610),
    (10, 8): ZonaTerritorial("ADELA ZAMUDIO", 10, 8, "NORESTE", -17.3985, -66.1510),
    (10, 11): ZonaTerritorial("ADELA ZAMUDIO", 10, 11, "SUDOESTE", -17.4100, -66.1615),
    (10, 12): ZonaTerritorial("ADELA ZAMUDIO", 10, 12, "SUDESTE", -17.4100, -66.1510),
    (11, 9): ZonaTerritorial("ADELA ZAMUDIO", 11, 9, "MUYURINA", -17.4075, -66.1390),
    (11, 13): ZonaTerritorial("ADELA ZAMUDIO", 11, 13, "LAS CUADRAS", -17.4140, -66.1430),
    (11, 16): ZonaTerritorial("ADELA ZAMUDIO", 11, 16, "ALALAY NORTE", -17.4120, -66.1480),
    (12, 2): ZonaTerritorial("ADELA ZAMUDIO", 12, 2, "SARCO", -17.3920, -66.1735),
    (12, 3): ZonaTerritorial("ADELA ZAMUDIO", 12, 3, "CALA CALA", -17.3890, -66.1680),
    (12, 4): ZonaTerritorial("ADELA ZAMUDIO", 12, 4, "QUERU QUERU", -17.3878, -66.1600),
    (12, 5): ZonaTerritorial("ADELA ZAMUDIO", 12, 5, "TUPURAYA", -17.3980, -66.1600),
    (12, 6): ZonaTerritorial("ADELA ZAMUDIO", 12, 6, "HIPODROMO", -17.4030, -66.1690),
}

DISTRICT_FALLBACK: dict[int, tuple[float, float]] = {
    1: (-17.3865, -66.1270),
    2: (-17.3780, -66.1705),
    3: (-17.3970, -66.1885),
    4: (-17.4130, -66.1880),
    5: (-17.4310, -66.1630),
    6: (-17.4140, -66.1460),
    7: (-17.4230, -66.1320),
    8: (-17.4460, -66.1170),
    9: (-17.4665, -66.2010),
    10: (-17.4040, -66.1560),
    11: (-17.4110, -66.1430),
    12: (-17.3940, -66.1660),
    13: (-17.3380, -66.1460),
    14: (-17.4410, -66.1210),
    15: (-17.4720, -66.1390),
}

DEFAULT_INFRA_RADIUS_DEG = 0.00028   # ~31 m
DEFAULT_MEDIDOR_RADIUS_DEG = 0.00014 # ~16 m


def is_inside_cercado_bounds(lat: float, lon: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = CERCADO_STRICT_BOUNDS
    return lat_min <= float(lat) <= lat_max and lon_min <= float(lon) <= lon_max


def point_in_ring(lat: float, lon: float, ring: list[tuple[float, float]] | None = None) -> bool:
    ring = ring or CERCADO_RING
    inside = False
    for i, j in zip(range(len(ring)), [len(ring) - 1] + list(range(len(ring) - 1))):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > lat) != (yj > lat):
            x_intersect = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lon < x_intersect:
                inside = not inside
    return inside


def is_inside_cercado(lat: float, lon: float) -> bool:
    if not is_inside_cercado_bounds(float(lat), float(lon)):
        return False
    return point_in_ring(float(lat), float(lon), CERCADO_RING)


def zone_metadata(distrito_id: int, zona_id: int) -> ZonaTerritorial | None:
    return TERRITORIO_ZONAS.get((int(distrito_id), int(zona_id)))


def zone_center(distrito_id: int, zona_id: int) -> Tuple[float, float]:
    d = int(distrito_id)
    z = int(zona_id)
    meta = zone_metadata(d, z)
    center = (meta.lat, meta.lon) if meta else DISTRICT_FALLBACK.get(d, (-17.414, -66.161))
    if not is_inside_cercado(center[0], center[1]):
        # Si se agrega una zona nueva con centro incorrecto, volvemos al distrito.
        return DISTRICT_FALLBACK.get(d, (-17.414, -66.161))
    return center


def stable_float(seed: str, salt: str) -> float:
    h = hashlib.sha256(f"{seed}:{salt}".encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def deterministic_point_near(center: tuple[float, float], seed: str, radius_deg: float) -> tuple[float, float]:
    angle = stable_float(seed, "angle") * 2 * math.pi
    radius0 = radius_deg * math.sqrt(stable_float(seed, "radius"))
    for factor in (1.0, 0.50, 0.25, 0.10, 0.0):
        radius = radius0 * factor
        lat = center[0] + math.sin(angle) * radius
        lon = center[1] + math.cos(angle) * radius
        if is_inside_cercado(lat, lon):
            return round(lat, 6), round(lon, 6)
    return round(center[0], 6), round(center[1], 6)


GATEWAY_SAFE_POINTS: dict[int, tuple[float, float]] = {
    1: (-17.3845, -66.1315), 2: (-17.3860, -66.1230), 3: (-17.3900, -66.1280), 4: (-17.3815, -66.1780),
    5: (-17.3790, -66.1690), 6: (-17.3730, -66.1800), 7: (-17.3955, -66.1860), 8: (-17.3990, -66.1765),
    9: (-17.4075, -66.1765), 10: (-17.4160, -66.1800), 11: (-17.4290, -66.1580), 12: (-17.4360, -66.1760),
    13: (-17.4215, -66.1510), 14: (-17.4140, -66.1460), 15: (-17.4195, -66.1340), 16: (-17.4250, -66.1305),
    17: (-17.3980, -66.1610), 18: (-17.3985, -66.1510), 19: (-17.4100, -66.1615), 20: (-17.4100, -66.1510),
    21: (-17.4075, -66.1390), 22: (-17.4140, -66.1430), 23: (-17.3920, -66.1735), 24: (-17.3890, -66.1680),
    25: (-17.4480, -66.1940), 26: (-17.4635, -66.1910), 27: (-17.4720, -66.2075), 28: (-17.4560, -66.1720),
    29: (-17.4610, -66.1430), 30: (-17.4740, -66.1390), 31: (-17.4820, -66.1340), 32: (-17.4450, -66.1185),
}


def gateway_safe_point(gateway_id: int) -> tuple[float, float]:
    # PDF actualizado: 14 radiobases. Si llega un ID antiguo 15..32, se
    # normaliza a 1..14 para evitar puntos fuera del mapa.
    gid = int(gateway_id or 1)
    if not 1 <= gid <= 14:
        gid = ((gid - 1) % 14) + 1
    point = GATEWAY_SAFE_POINTS.get(gid, DISTRICT_FALLBACK.get(((gid - 1) % 15) + 1, (-17.414, -66.161)))
    if not is_inside_cercado(point[0], point[1]):
        return (-17.414, -66.161)
    return point
