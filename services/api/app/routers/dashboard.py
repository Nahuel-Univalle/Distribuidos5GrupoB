"""Dashboard endpoints — KPIs y vistas estratégicas por rol.

Lee las tablas agregadas generadas por el seeder:
- resumen_dashboard_alcaldia
- resumen_dashboard_gerencia
- resumen_dashboard_contabilidad
- proyeccion_ingresos_por_categoria
- proyeccion_demanda_por_distrito
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.cassandra_client import cassandra_client
from app.core.redis_client import redis_client
from app.core.security import (
    ROLE_ALCALDIA,
    ROLE_CONTABILIDAD,
    ROLE_GERENCIA,
    current_user,
)

router = APIRouter()

PERIODO_DEFAULT = "2026-05"


def _periodo_seguro(periodo: str) -> str:
    periodo = (periodo or PERIODO_DEFAULT).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", periodo):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Periodo inválido. Use formato YYYY-MM")
    return periodo


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _row_get(row: dict, key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _sum_float(rows: list[dict], key: str) -> float:
    return round(sum(_to_float(_row_get(row, key)) for row in rows), 2)


def _sum_int(rows: list[dict], key: str) -> int:
    return sum(_to_int(_row_get(row, key)) for row in rows)


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return round(num / den, 2)


def _query_periodo(table: str, periodo: str) -> list[dict]:
    periodo = _periodo_seguro(periodo)
    return list(
        cassandra_client.execute_raw(
            f"SELECT * FROM {table} WHERE periodo='{periodo}'",
            profile="analytics",
        )
    )


def _query_all(sql: str) -> list[dict]:
    return list(cassandra_client.execute_raw(sql, profile="analytics"))


async def _cached_kpi(key: str, fn, ttl: int = 60):
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    value = fn()
    await redis_client.set(key, json.dumps(value, default=str), ttl_seconds=ttl)
    return value


def _require_role(user: dict, allowed: set[str]) -> None:
    if user.get("rol") not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol no autorizado para este dashboard")


@router.get("/kpis")
async def kpis(
    periodo: str = Query(PERIODO_DEFAULT, description="Periodo en formato YYYY-MM"),
    user: dict = Depends(current_user),
):
    periodo = _periodo_seguro(periodo)
    rol = user["rol"]

    if rol == ROLE_ALCALDIA:
        return await _cached_kpi(f"dash:kpis:alcaldia:{periodo}", lambda: _dashboard_alcaldia(periodo), ttl=120)

    if rol == ROLE_GERENCIA:
        return await _cached_kpi(f"dash:kpis:gerencia:{periodo}", lambda: _dashboard_gerencia(periodo), ttl=60)

    if rol == ROLE_CONTABILIDAD:
        return await _cached_kpi(f"dash:kpis:contabilidad:{periodo}", lambda: _dashboard_contabilidad(periodo), ttl=120)

    raise HTTPException(status.HTTP_403_FORBIDDEN, "Rol no autorizado")


@router.get("/alcaldia")
async def dashboard_alcaldia(
    periodo: str = Query(PERIODO_DEFAULT, description="Periodo en formato YYYY-MM"),
    user: dict = Depends(current_user),
):
    _require_role(user, {ROLE_ALCALDIA})
    periodo = _periodo_seguro(periodo)
    return await _cached_kpi(f"dash:alcaldia:{periodo}", lambda: _dashboard_alcaldia(periodo), ttl=120)


@router.get("/gerencia")
async def dashboard_gerencia(
    periodo: str = Query(PERIODO_DEFAULT, description="Periodo en formato YYYY-MM"),
    user: dict = Depends(current_user),
):
    _require_role(user, {ROLE_GERENCIA})
    periodo = _periodo_seguro(periodo)
    return await _cached_kpi(f"dash:gerencia:{periodo}", lambda: _dashboard_gerencia(periodo), ttl=60)


@router.get("/contabilidad")
async def dashboard_contabilidad(
    periodo: str = Query(PERIODO_DEFAULT, description="Periodo en formato YYYY-MM"),
    user: dict = Depends(current_user),
):
    _require_role(user, {ROLE_CONTABILIDAD})
    periodo = _periodo_seguro(periodo)
    return await _cached_kpi(f"dash:contabilidad:{periodo}", lambda: _dashboard_contabilidad(periodo), ttl=120)


@router.get("/resumen-general")
async def resumen_general(
    periodo: str = Query(PERIODO_DEFAULT, description="Periodo en formato YYYY-MM"),
    user: dict = Depends(current_user),
):
    periodo = _periodo_seguro(periodo)
    return await _cached_kpi(f"dash:general:{periodo}", lambda: _resumen_general(periodo), ttl=120)


def _dashboard_alcaldia(periodo: str) -> dict:
    rows = _query_periodo("resumen_dashboard_alcaldia", periodo)

    medidores_totales = _sum_int(rows, "medidores_totales")
    medidores_activos = _sum_int(rows, "medidores_activos")
    sensores_con_fallas = _sum_int(rows, "sensores_con_fallas")
    poblacion = _sum_int(rows, "poblacion_beneficiaria")
    consumo_total_m3 = _sum_float(rows, "consumo_total_m3")
    zonas_criticas = _sum_int(rows, "zonas_criticas")

    consumo_per_capita_litros = _safe_div(consumo_total_m3 * 1000, poblacion)
    cobertura_servicio = _safe_div(medidores_activos * 100, medidores_totales)

    por_distrito: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "distrito_id": 0,
            "poblacion_beneficiaria": 0,
            "medidores_totales": 0,
            "medidores_activos": 0,
            "sensores_con_fallas": 0,
            "consumo_total_m3": 0.0,
            "zonas_criticas": 0,
        }
    )

    zonas: list[dict[str, Any]] = []

    for row in rows:
        distrito_id = _to_int(row.get("distrito_id"))
        zona_id = _to_int(row.get("zona_id"))
        item = por_distrito[distrito_id]
        item["distrito_id"] = distrito_id
        item["poblacion_beneficiaria"] += _to_int(row.get("poblacion_beneficiaria"))
        item["medidores_totales"] += _to_int(row.get("medidores_totales"))
        item["medidores_activos"] += _to_int(row.get("medidores_activos"))
        item["sensores_con_fallas"] += _to_int(row.get("sensores_con_fallas"))
        item["consumo_total_m3"] += _to_float(row.get("consumo_total_m3"))
        item["zonas_criticas"] += _to_int(row.get("zonas_criticas"))

        zonas.append(
            {
                "distrito_id": distrito_id,
                "zona_id": zona_id,
                "poblacion_beneficiaria": _to_int(row.get("poblacion_beneficiaria")),
                "medidores_totales": _to_int(row.get("medidores_totales")),
                "medidores_activos": _to_int(row.get("medidores_activos")),
                "sensores_con_fallas": _to_int(row.get("sensores_con_fallas")),
                "consumo_total_m3": _to_float(row.get("consumo_total_m3")),
                "consumo_per_capita_litros": _to_float(row.get("consumo_per_capita_litros")),
                "cobertura_servicio": _to_float(row.get("cobertura_servicio")),
                "zonas_criticas": _to_int(row.get("zonas_criticas")),
            }
        )

    consumo_por_distrito = []
    for item in por_distrito.values():
        total = item["medidores_totales"] or 1
        item["consumo_total_m3"] = round(item["consumo_total_m3"], 2)
        item["cobertura_servicio"] = round((item["medidores_activos"] * 100) / total, 2)
        consumo_por_distrito.append(item)

    consumo_por_distrito.sort(key=lambda item: item["distrito_id"])
    zonas.sort(key=lambda item: (item["distrito_id"], item["zona_id"]))

    return {
        "periodo": periodo,
        "rol": ROLE_ALCALDIA,
        "titulo": "Dashboard Alcaldía",
        "kpis": {
            "poblacion_beneficiaria": poblacion,
            "medidores_totales": medidores_totales,
            "medidores_activos": medidores_activos,
            "sensores_con_fallas": sensores_con_fallas,
            "consumo_total_m3": consumo_total_m3,
            "consumo_per_capita_litros": consumo_per_capita_litros,
            "cobertura_servicio": cobertura_servicio,
            "zonas_criticas": zonas_criticas,
            "ods_6_indicador": round(cobertura_servicio, 2),
        },
        "consumo_por_distrito": consumo_por_distrito,
        "zonas": zonas,
    }


def _dashboard_gerencia(periodo: str) -> dict:
    rows = _query_periodo("resumen_dashboard_gerencia", periodo)

    consumo_total = _sum_float(rows, "consumo_total_m3")
    consumo_promedio_diario = _sum_float(rows, "consumo_promedio_diario_m3")
    pico_maximo = max((_to_float(row.get("pico_maximo_horario_m3")) for row in rows), default=0.0)
    activos = _sum_int(rows, "medidores_activos")
    inactivos = _sum_int(rows, "medidores_inactivos")
    fuera_servicio = _sum_int(rows, "medidores_fuera_servicio")
    con_error = _sum_int(rows, "medidores_con_error")
    lecturas_faltantes = _sum_int(rows, "lecturas_faltantes")
    lecturas_app_movil = _sum_int(rows, "lecturas_app_movil")

    top_zonas_demanda = []
    estado_por_zona = []

    for row in rows:
        item = {
            "distrito_id": _to_int(row.get("distrito_id")),
            "zona_id": _to_int(row.get("zona_id")),
            "consumo_total_m3": _to_float(row.get("consumo_total_m3")),
            "consumo_promedio_diario_m3": _to_float(row.get("consumo_promedio_diario_m3")),
            "pico_maximo_horario_m3": _to_float(row.get("pico_maximo_horario_m3")),
            "medidores_activos": _to_int(row.get("medidores_activos")),
            "medidores_inactivos": _to_int(row.get("medidores_inactivos")),
            "medidores_fuera_servicio": _to_int(row.get("medidores_fuera_servicio")),
            "medidores_con_error": _to_int(row.get("medidores_con_error")),
            "lecturas_faltantes": _to_int(row.get("lecturas_faltantes")),
            "lecturas_app_movil": _to_int(row.get("lecturas_app_movil")),
            "latencia_ingestion_ms": _to_float(row.get("latencia_ingestion_ms")),
        }
        top_zonas_demanda.append(item)
        estado_por_zona.append(item)

    top_zonas_demanda.sort(key=lambda item: item["consumo_total_m3"], reverse=True)
    estado_por_zona.sort(key=lambda item: (item["distrito_id"], item["zona_id"]))

    return {
        "periodo": periodo,
        "rol": ROLE_GERENCIA,
        "titulo": "Dashboard Gerencia",
        "kpis": {
            "consumo_total_m3": consumo_total,
            "consumo_promedio_diario_m3": consumo_promedio_diario,
            "pico_maximo_horario_m3": round(pico_maximo, 2),
            "medidores_activos": activos,
            "medidores_inactivos": inactivos,
            "medidores_fuera_servicio": fuera_servicio,
            "medidores_con_error": con_error,
            "lecturas_faltantes": lecturas_faltantes,
            "lecturas_app_movil": lecturas_app_movil,
            "latencia_promedio_ms": round(
                _safe_div(sum(_to_float(row.get("latencia_ingestion_ms")) for row in rows), len(rows) or 1),
                2,
            ),
        },
        "top_zonas_demanda": top_zonas_demanda[:10],
        "estado_por_zona": estado_por_zona,
        "estado_medidores": {
            "activos": activos,
            "inactivos": inactivos,
            "fuera_servicio": fuera_servicio,
            "con_error": con_error,
        },
    }


def _dashboard_contabilidad(periodo: str) -> dict:
    rows = _query_periodo("resumen_dashboard_contabilidad", periodo)

    monto_facturado = _sum_float(rows, "monto_facturado_bs")
    monto_recaudado = _sum_float(rows, "monto_recaudado_bs")
    cartera_vencida = _sum_float(rows, "cartera_vencida_bs")
    contratos_activos = _sum_int(rows, "contratos_activos")
    contratos_morosos = _sum_int(rows, "contratos_morosos")
    preavisos_emitidos = _sum_int(rows, "preavisos_emitidos")
    preavisos_entregados = _sum_int(rows, "preavisos_entregados")
    preavisos_fallidos = _sum_int(rows, "preavisos_fallidos")
    ticket_promedio = _safe_div(monto_facturado, contratos_activos)

    por_distrito: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "distrito_id": 0,
            "monto_facturado_bs": 0.0,
            "monto_recaudado_bs": 0.0,
            "cartera_vencida_bs": 0.0,
            "contratos_activos": 0,
            "contratos_morosos": 0,
        }
    )

    por_categoria: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "categoria_tarifa": "",
            "monto_facturado_bs": 0.0,
            "monto_recaudado_bs": 0.0,
            "cartera_vencida_bs": 0.0,
            "contratos_activos": 0,
            "contratos_morosos": 0,
        }
    )

    detalle = []

    for row in rows:
        distrito_id = _to_int(row.get("distrito_id"))
        categoria = row.get("categoria_tarifa") or "SIN_CATEGORIA"

        facturado = _to_float(row.get("monto_facturado_bs"))
        recaudado = _to_float(row.get("monto_recaudado_bs"))
        cartera = _to_float(row.get("cartera_vencida_bs"))
        activos = _to_int(row.get("contratos_activos"))
        morosos = _to_int(row.get("contratos_morosos"))

        d_item = por_distrito[distrito_id]
        d_item["distrito_id"] = distrito_id
        d_item["monto_facturado_bs"] += facturado
        d_item["monto_recaudado_bs"] += recaudado
        d_item["cartera_vencida_bs"] += cartera
        d_item["contratos_activos"] += activos
        d_item["contratos_morosos"] += morosos

        c_item = por_categoria[categoria]
        c_item["categoria_tarifa"] = categoria
        c_item["monto_facturado_bs"] += facturado
        c_item["monto_recaudado_bs"] += recaudado
        c_item["cartera_vencida_bs"] += cartera
        c_item["contratos_activos"] += activos
        c_item["contratos_morosos"] += morosos

        detalle.append(
            {
                "distrito_id": distrito_id,
                "categoria_tarifa": categoria,
                "monto_facturado_bs": facturado,
                "monto_recaudado_bs": recaudado,
                "cartera_vencida_bs": cartera,
                "contratos_activos": activos,
                "contratos_morosos": morosos,
                "preavisos_emitidos": _to_int(row.get("preavisos_emitidos")),
                "preavisos_entregados": _to_int(row.get("preavisos_entregados")),
                "preavisos_fallidos": _to_int(row.get("preavisos_fallidos")),
                "ticket_promedio_bs": _to_float(row.get("ticket_promedio_bs")),
            }
        )

    for items in (por_distrito.values(), por_categoria.values()):
        for item in items:
            item["monto_facturado_bs"] = round(item["monto_facturado_bs"], 2)
            item["monto_recaudado_bs"] = round(item["monto_recaudado_bs"], 2)
            item["cartera_vencida_bs"] = round(item["cartera_vencida_bs"], 2)
            item["ticket_promedio_bs"] = _safe_div(item["monto_facturado_bs"], item["contratos_activos"])

    proyeccion = _proyeccion_ingresos(periodo)

    return {
        "periodo": periodo,
        "rol": ROLE_CONTABILIDAD,
        "titulo": "Dashboard Contabilidad",
        "kpis": {
            "monto_facturado_bs": monto_facturado,
            "monto_recaudado_bs": monto_recaudado,
            "cartera_vencida_bs": cartera_vencida,
            "contratos_activos": contratos_activos,
            "contratos_morosos": contratos_morosos,
            "preavisos_emitidos": preavisos_emitidos,
            "preavisos_entregados": preavisos_entregados,
            "preavisos_fallidos": preavisos_fallidos,
            "ticket_promedio_bs": ticket_promedio,
            "porcentaje_mora": _safe_div(contratos_morosos * 100, contratos_activos),
            "efectividad_preavisos": _safe_div(preavisos_entregados * 100, preavisos_emitidos),
        },
        "facturacion_por_distrito": sorted(por_distrito.values(), key=lambda item: item["distrito_id"]),
        "facturacion_por_categoria": sorted(por_categoria.values(), key=lambda item: item["categoria_tarifa"]),
        "detalle": sorted(detalle, key=lambda item: (item["distrito_id"], item["categoria_tarifa"])),
        "proyeccion_ingresos": proyeccion,
    }


def _proyeccion_ingresos(periodo: str) -> list[dict[str, Any]]:
    rows = _query_periodo("proyeccion_ingresos_por_categoria", periodo)
    out = []
    for row in rows:
        out.append(
            {
                "categoria_tarifa": row.get("categoria_tarifa"),
                "consumo_m3": _to_float(row.get("consumo_m3")),
                "ingresos_estimados_bs": _to_float(row.get("ingresos_estimados_bs")),
                "ingresos_estimados_usd": _to_float(row.get("ingresos_estimados_usd")),
                "contratos": _to_int(row.get("contratos")),
            }
        )
    return sorted(out, key=lambda item: item["categoria_tarifa"] or "")


def _resumen_general(periodo: str) -> dict:
    alcaldia = _dashboard_alcaldia(periodo)
    gerencia = _dashboard_gerencia(periodo)
    contabilidad = _dashboard_contabilidad(periodo)

    return {
        "periodo": periodo,
        "kpis_generales": {
            "medidores_totales": alcaldia["kpis"].get("medidores_totales", 0),
            "medidores_activos": alcaldia["kpis"].get("medidores_activos", 0),
            "poblacion_beneficiaria": alcaldia["kpis"].get("poblacion_beneficiaria", 0),
            "consumo_total_m3": gerencia["kpis"].get("consumo_total_m3", 0),
            "monto_facturado_bs": contabilidad["kpis"].get("monto_facturado_bs", 0),
            "cartera_vencida_bs": contabilidad["kpis"].get("cartera_vencida_bs", 0),
        },
        "alcaldia": alcaldia["kpis"],
        "gerencia": gerencia["kpis"],
        "contabilidad": contabilidad["kpis"],
    }
