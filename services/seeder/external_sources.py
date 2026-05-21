"""Carga de CSV externos del Excel actualizado de Práctica 5.

Los CSV exportados desde los links/hojas del Excel se montan en Docker en:
    /data/external/

Archivos esperados:
    infraestructuras_cochabamba.csv  -> 80.000 infraestructuras
    contratos_agua.csv               -> 100.000 contratos
    medidores_iot.csv                -> 120.000 medidores IoT
    lecturas_iot.csv                 -> muestra de lecturas febrero-marzo-abril

Este módulo normaliza datos para que el seeder cumpla el PDF actualizado:
80k infraestructuras, 100k contratos, 120k medidores, 14 radiobases y 9 tarifas.
"""
from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


EXTERNAL_DIR = Path("/data/external")


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Lee CSV tolerando UTF-8 y latin-1."""
    if not path.exists():
        return []
    last_error: Exception | None = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return [dict(row) for row in csv.DictReader(f)]
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
    raise RuntimeError(f"No se pudo leer {path}: {last_error}")


def _first_not_empty(*values: str | None, default: str = "") -> str:
    for v in values:
        if v is not None and str(v).strip():
            return str(v).strip()
    return default


def only_digits(text: str | None) -> str:
    return re.sub(r"\D+", "", text or "")


def contrato_to_bigint(numero_contrato: str) -> int:
    digits = only_digits(numero_contrato)
    return int(digits or 0)


def stable_int(seed: str, modulo: int, offset: int = 0) -> int:
    h = hashlib.sha256(str(seed).encode()).digest()
    return offset + (int.from_bytes(h[:8], "big") % modulo)


def parse_date(value: str | None, fallback: date | None = None) -> date | None:
    text = (value or "").strip()
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d", "%m/%d/%y", "%m/%d/%Y", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return fallback


def parse_datetime(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%m/%d/%y %H:%M", "%m/%d/%Y %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    return None


def normalize_install_date(raw: str | None, seed: str) -> date:
    """El PDF pide instalación aleatoria entre 2020 y 2025-03-01."""
    min_d = date(2020, 1, 1)
    max_d = date(2025, 3, 1)
    d = parse_date(raw)
    if d and min_d <= d <= max_d:
        return d
    span = (max_d - min_d).days
    return min_d + timedelta(days=stable_int(seed, span + 1))


def normalize_mac(mac: str | None) -> str:
    text = (mac or "").strip().upper()
    parts = re.findall(r"[0-9A-F]{2}", text)
    if len(parts) >= 6:
        return ":".join(parts[:6])
    return text


def normalize_estado_medidor(raw: str | None) -> tuple[str, str, bool]:
    text = (raw or "").strip().upper()
    if text in {"OPERATIVO", "NUEVO"}:
        return "ACTIVO", text or "OPERATIVO", True
    if text == "MANTENIMIENTO":
        return "INACTIVO", "MANTENIMIENTO", False
    if text in {"DAÑADO", "DANADO"}:
        return "DAÑADO", "DAÑO_CAUDALIMETRO", False
    if text == "REACONDICIONADO":
        return "REEMPLAZADO", "REACONDICIONADO", False
    return "FUERA_SERVICIO", text or "SIN_REPORTE", False


def categoria_tarifa(row: dict[str, str]) -> str:
    sub = (row.get("subcategoria") or row.get("categoria_tarifa") or "").strip().upper()
    if sub in {"R1", "R2", "R3", "R4", "C", "CE", "I", "P", "S"}:
        return sub
    cat = (row.get("categoria") or "").strip().upper()
    aliases = {
        "RESIDENCIAL": "R3",
        "COMERCIAL": "C",
        "COMERCIAL ESPECIAL": "CE",
        "INDUSTRIAL": "I",
        "PREFERENCIAL": "P",
        "SOCIAL": "S",
    }
    return aliases.get(cat, "R3")


def tipo_infra_from_uso(uso: str | None) -> int:
    text = (uso or "").strip().upper()
    if "EDUC" in text:
        return 1
    if "SALUD" in text:
        return 2
    if "COMERCIAL" in text:
        return 6
    if "INDUSTR" in text:
        return 11
    if "MIXTO" in text:
        return 12
    return 9


@dataclass(frozen=True)
class ExternalInfra:
    numero_catastro: str
    propietario: str
    ci: str
    direccion: str
    zona_nombre: str
    distrito_id: int
    tipo_infra: int
    latitud_original: float | None = None
    longitud_original: float | None = None


@dataclass(frozen=True)
class ExternalContrato:
    numero_contrato_txt: str
    numero_contrato: int
    numero_catastro: str
    titular: str
    ci_titular: str
    categoria: str
    subcategoria: str
    medidor_iot: str
    fecha_contrato: date
    estado_contrato: str
    diametro_conexion: str
    tipo_servicio: str


@dataclass(frozen=True)
class ExternalMedidor:
    mac: str
    fecha_instalacion: date
    fecha_desinstalacion: date | None
    estado: str
    motivo_estado: str
    es_actual: bool
    modelo_id: int


@dataclass(frozen=True)
class ExternalLectura:
    mac: str
    lectura_anterior: int
    lectura_actual: int
    fecha_hora: datetime
    radiobase: int | None
    fecha_pago: datetime | None


@dataclass(frozen=True)
class ExternalSources:
    infraestructuras: list[ExternalInfra]
    contratos: list[ExternalContrato]
    medidores: list[ExternalMedidor]
    lecturas: list[ExternalLectura]

    @property
    def complete_for_base_seed(self) -> bool:
        return bool(self.infraestructuras and self.contratos and self.medidores)


def load_infraestructuras(external_dir: Path = EXTERNAL_DIR) -> list[ExternalInfra]:
    rows = _read_csv(external_dir / "infraestructuras_cochabamba.csv")
    out: list[ExternalInfra] = []
    for r in rows:
        try:
            distrito = int(float(_first_not_empty(r.get("distrito"), default="0")))
        except ValueError:
            distrito = 0
        if not (1 <= distrito <= 15):
            # La práctica se limita a Cochabamba/Cercado.
            continue
        lat = None
        lon = None
        try:
            lat = float(r.get("latitud") or "")
            lon = float(r.get("longitud") or "")
        except ValueError:
            pass
        out.append(ExternalInfra(
            numero_catastro=_first_not_empty(r.get("numero_catastro")),
            propietario=_first_not_empty(r.get("propietario"), default="SIN PROPIETARIO"),
            ci=_first_not_empty(r.get("ci"), default="0 CBBA"),
            direccion=_first_not_empty(r.get("direccion"), default="S/D"),
            zona_nombre=_first_not_empty(r.get("zona"), default="S/Z"),
            distrito_id=distrito,
            tipo_infra=tipo_infra_from_uso(r.get("uso_suelo")),
            latitud_original=lat,
            longitud_original=lon,
        ))
    return out


def load_contratos(external_dir: Path = EXTERNAL_DIR) -> list[ExternalContrato]:
    rows = _read_csv(external_dir / "contratos_agua.csv")
    out: list[ExternalContrato] = []
    for r in rows:
        numero_txt = _first_not_empty(r.get("numero_contrato"))
        fecha = parse_date(r.get("fecha_contrato"), fallback=date(2020, 1, 1)) or date(2020, 1, 1)
        out.append(ExternalContrato(
            numero_contrato_txt=numero_txt,
            numero_contrato=contrato_to_bigint(numero_txt),
            numero_catastro=_first_not_empty(r.get("numero_catastro")),
            titular=_first_not_empty(r.get("titular_contrato"), default="SIN TITULAR"),
            ci_titular=_first_not_empty(r.get("ci_titular"), default="0 CBBA"),
            categoria=_first_not_empty(r.get("categoria"), default="Residencial"),
            subcategoria=categoria_tarifa(r),
            medidor_iot=normalize_mac(r.get("medidor_iot")),
            fecha_contrato=fecha,
            estado_contrato=_first_not_empty(r.get("estado_contrato"), default="ACTIVO").upper(),
            diametro_conexion=_first_not_empty(r.get("diametro_conexion"), default='1/2"'),
            tipo_servicio=_first_not_empty(r.get("tipo_servicio"), default="Agua Potable"),
        ))
    return out


def load_medidores(external_dir: Path = EXTERNAL_DIR) -> list[ExternalMedidor]:
    rows = _read_csv(external_dir / "medidores_iot.csv")
    out: list[ExternalMedidor] = []
    for r in rows:
        mac = normalize_mac(r.get("medidor_iot"))
        estado, motivo, actual = normalize_estado_medidor(r.get("estado"))
        fecha_inst = normalize_install_date(r.get("fecha_instalacion"), mac)
        fecha_des = parse_date(r.get("fecha_desinstalacion"))
        try:
            modelo_id = int(float(r.get("tipo_medidor_id") or 1))
        except ValueError:
            modelo_id = 1
        modelo_id = max(1, min(5, modelo_id))
        out.append(ExternalMedidor(
            mac=mac,
            fecha_instalacion=fecha_inst,
            fecha_desinstalacion=fecha_des,
            estado=estado,
            motivo_estado=motivo,
            es_actual=actual,
            modelo_id=modelo_id,
        ))
    return out


def load_lecturas(external_dir: Path = EXTERNAL_DIR, max_rows: int = 0) -> list[ExternalLectura]:
    rows = _read_csv(external_dir / "lecturas_iot.csv")
    out: list[ExternalLectura] = []
    for r in rows:
        dt = parse_datetime(r.get("fechaHoraLectura"))
        if dt is None:
            continue
        try:
            anterior = int(float(r.get("lecturaAnterior") or 0))
            actual = int(float(r.get("LecturaActual") or 0))
        except ValueError:
            continue
        rb_txt = (r.get("radiobase") or "").strip()
        radiobase = None
        if rb_txt:
            try:
                radiobase = int(float(rb_txt))
            except ValueError:
                radiobase = None
        out.append(ExternalLectura(
            mac=normalize_mac(r.get("medidor_iot")),
            lectura_anterior=anterior,
            lectura_actual=actual,
            fecha_hora=dt,
            radiobase=radiobase if radiobase and 1 <= radiobase <= 14 else None,
            fecha_pago=parse_datetime(r.get("fecha_pago")),
        ))
        if max_rows and len(out) >= max_rows:
            break
    return out


def load_external_sources(external_dir: Path = EXTERNAL_DIR, load_lecturas_csv: bool = False, max_lecturas: int = 0) -> ExternalSources:
    return ExternalSources(
        infraestructuras=load_infraestructuras(external_dir),
        contratos=load_contratos(external_dir),
        medidores=load_medidores(external_dir),
        lecturas=load_lecturas(external_dir, max_lecturas) if load_lecturas_csv else [],
    )
