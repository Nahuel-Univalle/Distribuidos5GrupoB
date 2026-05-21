"""Endpoints geoespaciales para el dashboard de mapa.

No dependen de descargar el mapa digital municipal. El frontend usa una capa
GeoJSON aproximada generada desde el Excel/CSV y estos endpoints le agregan
estadísticas reales desde Cassandra.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import current_user

router = APIRouter()


async def _cached(key: str, fn, ttl: int = 120):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    value = fn()
    await redis_client.set(key, json.dumps(value, default=str), ttl_seconds=ttl)
    return value


def _safe_uuid(v: Any) -> Any:
    return str(v) if hasattr(v, "hex") else v


# Caja estricta de seguridad visual para Cercado.
# (lat_min, lat_max, lon_min, lon_max)
CERCADO_STRICT_BOUNDS = (-17.5120, -17.3180, -66.2380, -66.1080)

# Polígono conservador del municipio Cercado para filtro/fallback visual.
CERCADO_RING = [
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

# Centros seguros por clave compuesta (distrito_id, zona_id), derivados de la
# tabla territorial de la presentación de Práctica 5. No usar zona_id solo.
SAFE_ZONE_CENTERS: dict[tuple[int, int], tuple[float, float]] = {
    (1, 24): (-17.3845, -66.1315), (1, 25): (-17.3860, -66.1230), (1, 26): (-17.3900, -66.1280),
    (2, 1): (-17.3815, -66.1780), (2, 3): (-17.3790, -66.1690), (2, 22): (-17.3730, -66.1800), (2, 23): (-17.3760, -66.1680), (2, 24): (-17.3820, -66.1610),
    (13, 24): (-17.3380, -66.1460),
    (3, 2): (-17.3955, -66.1860), (3, 6): (-17.3990, -66.1765), (3, 21): (-17.3910, -66.1940), (3, 27): (-17.3978, -66.2010), (3, 37): (-17.4040, -66.1860),
    (4, 6): (-17.4075, -66.1765), (4, 10): (-17.4160, -66.1800), (4, 27): (-17.4090, -66.1900), (4, 28): (-17.4185, -66.1970),
    (5, 12): (-17.4290, -66.1580), (5, 14): (-17.4360, -66.1760), (5, 15): (-17.4265, -66.1605), (5, 16): (-17.4215, -66.1510), (5, 17): (-17.4380, -66.1530),
    (8, 18): (-17.4420, -66.1160), (8, 20): (-17.4490, -66.1140), (8, 34): (-17.4470, -66.1210),
    (6, 16): (-17.4140, -66.1460),
    (7, 16): (-17.4195, -66.1340), (7, 19): (-17.4250, -66.1305),
    (14, 19): (-17.4375, -66.1220), (14, 20): (-17.4450, -66.1185),
    (9, 14): (-17.4480, -66.1940), (9, 28): (-17.4385, -66.2110), (9, 29): (-17.4635, -66.1910), (9, 30): (-17.4720, -66.2075), (9, 31): (-17.4595, -66.2210), (9, 32): (-17.4560, -66.1720), (9, 35): (-17.4810, -66.1980), (9, 36): (-17.4650, -66.2290),
    (15, 32): (-17.4610, -66.1430), (15, 33): (-17.4740, -66.1390), (15, 35): (-17.4820, -66.1340),
    (10, 7): (-17.3980, -66.1610), (10, 8): (-17.3985, -66.1510), (10, 11): (-17.4100, -66.1615), (10, 12): (-17.4100, -66.1510),
    (11, 9): (-17.4075, -66.1390), (11, 13): (-17.4140, -66.1430), (11, 16): (-17.4120, -66.1480),
    (12, 2): (-17.3920, -66.1735), (12, 3): (-17.3890, -66.1680), (12, 4): (-17.3878, -66.1600), (12, 5): (-17.3980, -66.1600), (12, 6): (-17.4030, -66.1690),
}

DISTRICT_FALLBACK = {
    1: (-17.3865, -66.1270), 2: (-17.3780, -66.1705), 3: (-17.3970, -66.1885),
    4: (-17.4130, -66.1880), 5: (-17.4310, -66.1630), 6: (-17.4140, -66.1460),
    7: (-17.4230, -66.1320), 8: (-17.4460, -66.1170), 9: (-17.4665, -66.2010),
    10: (-17.4040, -66.1560), 11: (-17.4110, -66.1430), 12: (-17.3940, -66.1660),
    13: (-17.3380, -66.1460), 14: (-17.4410, -66.1210), 15: (-17.4720, -66.1390),
}

GATEWAY_SAFE_POINTS = {
    1: (-17.3845, -66.1315), 2: (-17.3860, -66.1230), 3: (-17.3900, -66.1280), 4: (-17.3815, -66.1780),
    5: (-17.3790, -66.1690), 6: (-17.3730, -66.1800), 7: (-17.3955, -66.1860), 8: (-17.3990, -66.1765),
    9: (-17.4075, -66.1765), 10: (-17.4160, -66.1800), 11: (-17.4290, -66.1580), 12: (-17.4360, -66.1760),
    13: (-17.4215, -66.1510), 14: (-17.4140, -66.1460), 15: (-17.4195, -66.1340), 16: (-17.4250, -66.1305),
    17: (-17.3980, -66.1610), 18: (-17.3985, -66.1510), 19: (-17.4100, -66.1615), 20: (-17.4100, -66.1510),
    21: (-17.4075, -66.1390), 22: (-17.4140, -66.1430), 23: (-17.3920, -66.1735), 24: (-17.3890, -66.1680),
    25: (-17.4480, -66.1940), 26: (-17.4635, -66.1910), 27: (-17.4720, -66.2075), 28: (-17.4560, -66.1720),
    29: (-17.4610, -66.1430), 30: (-17.4740, -66.1390), 31: (-17.4820, -66.1340), 32: (-17.4450, -66.1185),
}


def _inside_strict_bounds(lat: float, lon: float) -> bool:
    lat_min, lat_max, lon_min, lon_max = CERCADO_STRICT_BOUNDS
    return lat_min <= float(lat) <= lat_max and lon_min <= float(lon) <= lon_max


def _point_in_ring(lat: float, lon: float) -> bool:
    if not _inside_strict_bounds(lat, lon):
        return False
    inside = False
    ring = CERCADO_RING
    for i, j in zip(range(len(ring)), [len(ring) - 1] + list(range(len(ring) - 1))):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > lat) != (yj > lat):
            x_intersect = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lon < x_intersect:
                inside = not inside
    return inside


def _zone_center(distrito_id: Any, zona_id: Any) -> tuple[float, float]:
    try:
        d = int(distrito_id or 0)
        z = int(zona_id or 0)
    except Exception:
        return (-17.414, -66.161)
    return SAFE_ZONE_CENTERS.get((d, z), DISTRICT_FALLBACK.get(d, (-17.414, -66.161)))


def _safe_point_for_row(row: dict, prefix: str = "med") -> tuple[float, float]:
    # API defensiva: aunque Cassandra aún tenga coordenadas viejas, el mapa se
    # pinta con coordenadas seguras por distrito+zona.
    import hashlib, math
    center = _zone_center(row.get("distrito_id"), row.get("zona_id"))
    seed = str(row.get("medidor_id") or row.get("infraestructura_id") or row.get("numero_contrato") or row.get("zona_id") or "x")
    h = hashlib.sha256(f"{prefix}:{seed}".encode()).digest()
    a = int.from_bytes(h[:8], "big") / 2**64 * 2 * math.pi
    r = 0.00012 * math.sqrt(int.from_bytes(h[8:16], "big") / 2**64)
    lat = center[0] + math.sin(a) * r
    lon = center[1] + math.cos(a) * r
    if not _point_in_ring(lat, lon):
        lat, lon = center
    return round(lat, 6), round(lon, 6)


def _gateway_safe_point(gateway_id: Any) -> tuple[float, float]:
    try:
        gid = int(gateway_id or 0)
    except Exception:
        gid = 0
    return GATEWAY_SAFE_POINTS.get(gid, DISTRICT_FALLBACK.get(((gid - 1) % 15) + 1, (-17.414, -66.161)))


def _coords_inside_cercado(row: dict) -> bool:
    lat = row.get("latitud")
    lon = row.get("longitud")
    if lat is None or lon is None:
        return True
    try:
        return _point_in_ring(float(lat), float(lon))
    except Exception:
        return False


def _is_cercado_district(value: Any) -> bool:
    """El mapa de Denis debe representar solo el municipio de Cercado."""
    try:
        d = int(value or 0)
    except Exception:
        return False
    return 1 <= d <= 15


@router.get("/resumen")
async def resumen_mapa(_u: dict = Depends(current_user)):
    """Totales que se muestran sobre el mapa."""
    def _q():
        estados: Counter[str] = Counter()
        categorias: Counter[str] = Counter()
        gateways: Counter[int] = Counter()
        total = 0
        for r in cassandra_client.execute_raw(
            "SELECT estado, categoria_tarifa, gateway_id, distrito_id FROM medidores",
            profile="analytics",
        ):
            if not _is_cercado_district(r.get("distrito_id")):
                continue
            total += 1
            estados[r.get("estado") or "SIN_ESTADO"] += 1
            categorias[r.get("categoria_tarifa") or "SIN_CATEGORIA"] += 1
            gateways[r.get("gateway_id") or 0] += 1
        infra = sum(1 for r in cassandra_client.execute_raw(
            "SELECT infraestructura_id, distrito_id FROM infraestructuras", profile="analytics"
        ) if _is_cercado_district(r.get("distrito_id")))
        return {
            "infraestructuras": infra,
            "medidores": total,
            "activos": estados.get("ACTIVO", 0),
            "fuera_servicio": estados.get("FUERA_SERVICIO", 0),
            "historicos": estados.get("REEMPLAZADO", 0) + estados.get("DAÑADO", 0) + estados.get("RETIRADO", 0),
            "por_estado": dict(estados),
            "por_categoria": dict(categorias),
            "gateways_con_medidores": len([g for g, n in gateways.items() if g and n]),
        }
    return await _cached("mapa:resumen", _q, ttl=120)


@router.get("/zonas")
async def zonas_mapa(
    estado: str | None = Query(default=None),
    distrito_id: int | None = Query(default=None),
    zona_id: int | None = Query(default=None),
    categoria: str | None = Query(default=None),
    gateway_id: int | None = Query(default=None),
    _u: dict = Depends(current_user),
):
    """Estadísticas por distrito/zona para pintar mapa.

    IMPORTANTE: aplica los mismos filtros que el frontend. Si el usuario elige
    Distrito 1, R3 o FUERA_SERVICIO, las zonas/burbujas que no tienen registros
    coincidentes devuelven medidores=0 y el frontend las oculta.
    """
    estado_norm = (estado or "TODOS").upper()
    categoria_norm = (categoria or "TODAS").upper()

    def _q():
        zonas: dict[tuple[int, int], dict[str, Any]] = {}
        for z in cassandra_client.execute_raw(
            "SELECT distrito_id, zona_id, nombre, gateway_id FROM zonas",
            profile="analytics",
        ):
            if not _is_cercado_district(z.get("distrito_id")):
                continue
            if distrito_id and int(z["distrito_id"]) != int(distrito_id):
                continue
            if zona_id and int(z["zona_id"]) != int(zona_id):
                continue
            if gateway_id and int(z.get("gateway_id") or 0) != int(gateway_id):
                continue
            key = (z["distrito_id"], z["zona_id"])
            zonas[key] = {
                "distrito_id": z["distrito_id"],
                "zona_id": z["zona_id"],
                "zona": z.get("nombre") or "",
                "gateway_id": z.get("gateway_id"),
                "medidores": 0,
                "activos": 0,
                "fuera_servicio": 0,
                "historicos": 0,
                "consumo_litros": 0,
                "lat_sum": 0.0,
                "lon_sum": 0.0,
                "coord_count": 0,
            }

        for r in cassandra_client.execute_raw(
            "SELECT distrito_id, zona_id, estado, categoria_tarifa, gateway_id, latitud, longitud FROM medidores",
            profile="analytics",
        ):
            if not _is_cercado_district(r.get("distrito_id")):
                continue
            if distrito_id and int(r.get("distrito_id") or 0) != int(distrito_id):
                continue
            if zona_id and int(r.get("zona_id") or 0) != int(zona_id):
                continue
            if gateway_id and int(r.get("gateway_id") or 0) != int(gateway_id):
                continue
            if estado_norm != "TODOS" and (r.get("estado") or "").upper() != estado_norm:
                continue
            if categoria_norm != "TODAS" and (r.get("categoria_tarifa") or "").upper() != categoria_norm:
                continue

            key = (r["distrito_id"], r["zona_id"])
            item = zonas.setdefault(key, {
                "distrito_id": r["distrito_id"], "zona_id": r["zona_id"], "zona": "",
                "gateway_id": r.get("gateway_id"), "medidores": 0, "activos": 0,
                "fuera_servicio": 0, "historicos": 0, "consumo_litros": 0,
                "lat_sum": 0.0, "lon_sum": 0.0, "coord_count": 0,
            })
            item["medidores"] += 1
            lat, lon = _safe_point_for_row(r, prefix="zona")
            item["lat_sum"] += float(lat)
            item["lon_sum"] += float(lon)
            item["coord_count"] += 1
            est = r.get("estado")
            if est == "ACTIVO":
                item["activos"] += 1
            elif est == "FUERA_SERVICIO":
                item["fuera_servicio"] += 1
            elif est in {"REEMPLAZADO", "DAÑADO", "RETIRADO"}:
                item["historicos"] += 1

        # Consumo: se filtra por distrito/zona y categoría cuando sea posible.
        for r in cassandra_client.execute_raw(
            "SELECT distrito_id, zona_id, categoria_tarifa, consumo_litros FROM lecturas_por_zona_dia",
            profile="analytics",
        ):
            if not _is_cercado_district(r.get("distrito_id")):
                continue
            if distrito_id and int(r.get("distrito_id") or 0) != int(distrito_id):
                continue
            if zona_id and int(r.get("zona_id") or 0) != int(zona_id):
                continue
            if categoria_norm != "TODAS" and (r.get("categoria_tarifa") or "").upper() != categoria_norm:
                continue
            key = (r["distrito_id"], r["zona_id"])
            if key in zonas and zonas[key]["medidores"] > 0:
                zonas[key]["consumo_litros"] += r.get("consumo_litros") or 0

        out = []
        for item in zonas.values():
            coord_count = item.pop("coord_count", 0) or 0
            lat_sum = item.pop("lat_sum", 0.0)
            lon_sum = item.pop("lon_sum", 0.0)
            if coord_count:
                item["centro_lat"] = lat_sum / coord_count
                item["centro_lon"] = lon_sum / coord_count
            else:
                item["centro_lat"], item["centro_lon"] = _zone_center(item.get("distrito_id"), item.get("zona_id"))
            out.append(item)
        return sorted(out, key=lambda x: (x["distrito_id"], x["zona_id"]))

    cache_key = f"mapa:zonas:{estado_norm}:{distrito_id}:{zona_id}:{categoria_norm}:{gateway_id}"
    return await _cached(cache_key, _q, ttl=90)


@router.get("/gateways")
async def gateways_mapa(_u: dict = Depends(current_user)):
    """32 gateways/radiobases simulados para el mapa."""
    def _q():
        counts: Counter[int] = Counter()
        for r in cassandra_client.execute_raw("SELECT gateway_id, distrito_id FROM medidores", profile="analytics"):
            if _is_cercado_district(r.get("distrito_id")):
                counts[r.get("gateway_id") or 0] += 1
        out = []
        for g in cassandra_client.execute_raw(
            "SELECT gateway_id, nombre, latitud, longitud FROM gateways",
            profile="analytics",
        ):
            gid = g["gateway_id"]
            lat, lon = _gateway_safe_point(gid)
            item = {
                "gateway_id": gid,
                "nombre": g.get("nombre") or f"Gateway {gid}",
                "latitud": lat,
                "longitud": lon,
                "medidores": counts.get(gid, 0),
            }
            if counts.get(gid, 0) > 0 and _point_in_ring(float(lat), float(lon)):
                out.append(item)
        return sorted(out, key=lambda x: x["gateway_id"])
    return await _cached("mapa:gateways", _q, ttl=300)


@router.get("/medidores-sample")
async def medidores_sample(
    limit: int = Query(2500, ge=1, le=10000),
    estado: str | None = Query(default=None),
    distrito_id: int | None = Query(default=None),
    zona_id: int | None = Query(default=None),
    categoria: str | None = Query(default=None),
    gateway_id: int | None = Query(default=None),
    _u: dict = Depends(current_user),
):
    """Muestra de puntos para no saturar Leaflet con 120k marcadores.

    Filtramos en servidor para que al elegir Distrito 1, por ejemplo, no se
    mezclen puntos de otros distritos por venir de una muestra LIMIT arbitraria.
    """
    def _q():
        rows = cassandra_client.execute_raw(
            f"SELECT medidor_id, mac, numero_serie, numero_contrato, estado, categoria_tarifa, "
            f"gateway_id, distrito_id, zona_id, latitud, longitud, fecha_instalacion, motivo_estado "
            f"FROM medidores",
            profile="analytics",
        )
        out = []
        for r in rows:
            if not _is_cercado_district(r.get("distrito_id")):
                continue
            if estado and estado.upper() != "TODOS" and (r.get("estado") or "").upper() != estado.upper():
                continue
            if distrito_id and int(r.get("distrito_id") or 0) != int(distrito_id):
                continue
            if zona_id and int(r.get("zona_id") or 0) != int(zona_id):
                continue
            if categoria and categoria.upper() != "TODAS" and (r.get("categoria_tarifa") or "").upper() != categoria.upper():
                continue
            if gateway_id and int(r.get("gateway_id") or 0) != int(gateway_id):
                continue
            item = {k: _safe_uuid(v) for k, v in r.items()}
            lat, lon = _safe_point_for_row(r, prefix="medidor")
            item["latitud"] = lat
            item["longitud"] = lon
            out.append(item)
            if len(out) >= int(limit):
                break
        return out
    return await _cached(f"mapa:sample:{limit}:{estado}:{distrito_id}:{zona_id}:{categoria}:{gateway_id}", _q, ttl=60)
