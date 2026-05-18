"""Repara coordenadas geográficas de datos SEMAPA ya poblados.

Uso principal:
    docker compose run --rm seeder python repair_geo.py

Qué hace:
- Reubica infraestructuras y medidores con la clave compuesta (distrito_id, zona_id).
- Mantiene todos los puntos dentro del municipio Cercado.
- Reduce la dispersión para que no crucen límites distritales visuales.
- No altera personas, contratos, tarifas, modelos, estados ni cantidades.

Después de correrlo:
    docker exec semapa-redis redis-cli FLUSHALL
    docker compose restart api-1 api-2 web nginx
"""
from __future__ import annotations

from typing import Iterable

from cassandra.concurrent import execute_concurrent_with_args
from loguru import logger
from tqdm import tqdm

from cassandra_io import connect
from geo_reference import (
    DEFAULT_INFRA_RADIUS_DEG,
    DEFAULT_MEDIDOR_RADIUS_DEG,
    deterministic_point_near,
    is_inside_cercado,
    zone_center,
    gateway_safe_point,
)


def chunks(items: list[tuple], size: int) -> Iterable[list[tuple]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def main() -> None:
    cluster, session = connect()
    logger.info("Reparando coordenadas SOLO dentro de Cercado por distrito_id + zona_id...")

    ps_infra = session.prepare("UPDATE infraestructuras SET latitud=?, longitud=? WHERE infraestructura_id=?")
    ps_med = session.prepare("UPDATE medidores SET latitud=?, longitud=? WHERE medidor_id=?")
    ps_gw = session.prepare("UPDATE gateways SET latitud=?, longitud=? WHERE gateway_id=?")

    infra_rows: list[tuple] = []
    infra_fuera = 0
    for r in session.execute("SELECT infraestructura_id, distrito_id, zona_id FROM infraestructuras"):
        center = zone_center(r.distrito_id, r.zona_id)
        lat, lon = deterministic_point_near(center, f"infra:{r.infraestructura_id}", DEFAULT_INFRA_RADIUS_DEG)
        if not is_inside_cercado(lat, lon):
            infra_fuera += 1
            lat, lon = center
        infra_rows.append((lat, lon, r.infraestructura_id))

    for batch in tqdm(list(chunks(infra_rows, 1000)), desc="infraestructuras"):
        execute_concurrent_with_args(session, ps_infra, batch, concurrency=100)

    med_rows: list[tuple] = []
    med_fuera = 0
    for r in session.execute("SELECT medidor_id, distrito_id, zona_id FROM medidores"):
        center = zone_center(r.distrito_id, r.zona_id)
        lat, lon = deterministic_point_near(center, f"med:{r.medidor_id}", DEFAULT_MEDIDOR_RADIUS_DEG)
        if not is_inside_cercado(lat, lon):
            med_fuera += 1
            lat, lon = center
        med_rows.append((lat, lon, r.medidor_id))

    for batch in tqdm(list(chunks(med_rows, 1000)), desc="medidores"):
        execute_concurrent_with_args(session, ps_med, batch, concurrency=120)

    gw_rows: list[tuple] = []
    gw_fuera = 0
    for r in session.execute("SELECT gateway_id FROM gateways"):
        lat, lon = gateway_safe_point(r.gateway_id)
        if not is_inside_cercado(lat, lon):
            gw_fuera += 1
            lat, lon = -17.414, -66.161
        gw_rows.append((lat, lon, r.gateway_id))

    for batch in tqdm(list(chunks(gw_rows, 1000)), desc="gateways"):
        execute_concurrent_with_args(session, ps_gw, batch, concurrency=32)

    logger.success(
        f"Coordenadas reparadas: {len(infra_rows)} infraestructuras, "
        f"{len(med_rows)} medidores y {len(gw_rows)} gateways"
    )
    logger.info(f"Validación interna: fuera_de_cercado infra={infra_fuera} medidores={med_fuera} gateways={gw_fuera}")
    logger.info("Luego ejecuta: docker exec semapa-redis redis-cli FLUSHALL")
    cluster.shutdown()


if __name__ == "__main__":
    main()
