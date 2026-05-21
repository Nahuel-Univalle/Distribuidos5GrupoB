import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup, Tooltip, useMap } from "react-leaflet";
import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import "leaflet.heat";
import {
  Activity,
  Antenna,
  BarChart3,
  Building2,
  CircleDot,
  Filter,
  Flame,
  Layers,
  MapPinned,
  RadioTower,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Waves,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import { COCHABAMBA_ZONAS_GEOJSON } from "../data/cochabambaZonas";

type EstadoFiltro = "TODOS" | "ACTIVO" | "INACTIVO" | "FUERA_SERVICIO" | "REEMPLAZADO" | "DAÑADO" | "RETIRADO";
type CategoriaFiltro = "TODAS" | "R1" | "R2" | "R3" | "R4" | "C" | "CE" | "I" | "P" | "S";
type CapaAnalitica = "calor" | "burbujas" | "puntos" | "mixto";
type MetricaMapa = "consumo" | "medidores" | "fallas" | "activos";

interface ZonaApi {
  distrito_id: number;
  zona_id: number;
  zona: string;
  gateway_id?: number;
  medidores: number;
  activos: number;
  fuera_servicio: number;
  historicos: number;
  consumo_litros: number;
  infraestructuras_base?: number;
  centro_lat?: number;
  centro_lon?: number;
  sub_alcaldia?: string;
}

interface GatewayApi {
  gateway_id: number;
  nombre: string;
  latitud: number;
  longitud: number;
  medidores: number;
}

interface MedidorApi {
  medidor_id: string;
  mac: string;
  numero_serie: string;
  numero_contrato: number;
  estado: string;
  categoria_tarifa: string;
  gateway_id: number;
  distrito_id: number;
  zona_id: number;
  latitud: number;
  longitud: number;
  fecha_instalacion?: string;
  motivo_estado?: string;
}

interface HoraPicoApi {
  hora: number;
  consumo_litros: number;
}

interface ResumenMapaApi {
  infraestructuras?: number;
  medidores?: number;
  activos?: number;
  fuera_servicio?: number;
  historicos?: number;
  por_estado?: Record<string, number>;
  por_categoria?: Record<string, number>;
  gateways_con_medidores?: number;
}

const CENTRO_CBB: [number, number] = [-17.414, -66.161];
const WMS_BASE = "http://mapadigital.cochabamba.bo/mapcache";
const OFFICIAL_DISTRICTS_URL =
  "https://cdn.jsdelivr.net/gh/ciudatoslab/20-distritos-en-cochabamba@main/distritos_cbba-2.geojson";
const OFFICIAL_DISTRICTS_RAW_URL =
  "https://raw.githubusercontent.com/ciudatoslab/20-distritos-en-cochabamba/main/distritos_cbba-2.geojson";
const SAMPLE_OPTIONS = [1000, 2500, 4000, 8000, 10000];

// Fallback aproximado del límite del municipio Cercado.
// En ejecución normal se usa la unión visual de los distritos; esto solo se usa
// si el navegador no puede descargar el GeoJSON del repositorio.
const CERCADO_FALLBACK_RING: Array<[number, number]> = [
  [-17.3180, -66.1600],
  [-17.3360, -66.1250],
  [-17.3740, -66.1160],
  [-17.4050, -66.1150],
  [-17.4380, -66.1080],
  [-17.4660, -66.1160],
  [-17.4920, -66.1360],
  [-17.5060, -66.1900],
  [-17.4880, -66.2320],
  [-17.4500, -66.2320],
  [-17.4200, -66.2220],
  [-17.3880, -66.2140],
  [-17.3560, -66.1980],
  [-17.3180, -66.1600],
];


const CERCADO_STRICT_BOUNDS = { latMin: -17.5120, latMax: -17.3180, lonMin: -66.2380, lonMax: -66.1080 };
function insideStrictCercadoBounds(lat: number, lon: number): boolean {
  return lat >= CERCADO_STRICT_BOUNDS.latMin && lat <= CERCADO_STRICT_BOUNDS.latMax && lon >= CERCADO_STRICT_BOUNDS.lonMin && lon <= CERCADO_STRICT_BOUNDS.lonMax;
}

const SAFE_ZONE_CENTER_BY_KEY: Record<string, [number, number]> = {
  "1-24": [-17.3845, -66.1315], "1-25": [-17.3860, -66.1230], "1-26": [-17.3900, -66.1280],
  "2-1": [-17.3815, -66.1780], "2-3": [-17.3790, -66.1690], "2-22": [-17.3730, -66.1800], "2-23": [-17.3760, -66.1680], "2-24": [-17.3820, -66.1610],
  "13-24": [-17.3380, -66.1460],
  "3-2": [-17.3955, -66.1860], "3-6": [-17.3990, -66.1765], "3-21": [-17.3910, -66.1940], "3-27": [-17.3978, -66.2010], "3-37": [-17.4040, -66.1860],
  "4-6": [-17.4075, -66.1765], "4-10": [-17.4160, -66.1800], "4-27": [-17.4090, -66.1900], "4-28": [-17.4185, -66.1970],
  "5-12": [-17.4290, -66.1580], "5-14": [-17.4360, -66.1760], "5-15": [-17.4265, -66.1605], "5-16": [-17.4215, -66.1510], "5-17": [-17.4380, -66.1530],
  "8-18": [-17.4420, -66.1160], "8-20": [-17.4490, -66.1140], "8-34": [-17.4470, -66.1210],
  "6-16": [-17.4140, -66.1460],
  "7-16": [-17.4195, -66.1340], "7-19": [-17.4250, -66.1305], "14-19": [-17.4375, -66.1220], "14-20": [-17.4450, -66.1185],
  "9-14": [-17.4480, -66.1940], "9-28": [-17.4385, -66.2110], "9-29": [-17.4635, -66.1910], "9-30": [-17.4720, -66.2075], "9-31": [-17.4595, -66.2210], "9-32": [-17.4560, -66.1720], "9-35": [-17.4810, -66.1980], "9-36": [-17.4650, -66.2290],
  "15-32": [-17.4610, -66.1430], "15-33": [-17.4740, -66.1390], "15-35": [-17.4820, -66.1340],
  "10-7": [-17.3980, -66.1610], "10-8": [-17.3985, -66.1510], "10-11": [-17.4100, -66.1615], "10-12": [-17.4100, -66.1510],
  "11-9": [-17.4075, -66.1390], "11-13": [-17.4140, -66.1430], "11-16": [-17.4120, -66.1480],
  "12-2": [-17.3920, -66.1735], "12-3": [-17.3890, -66.1680], "12-4": [-17.3878, -66.1600], "12-5": [-17.3980, -66.1600], "12-6": [-17.4030, -66.1690],
};
function safeCenterForZone(distritoId: number, zonaId: number, fallback: [number, number] = CENTRO_CBB): [number, number] {
  return SAFE_ZONE_CENTER_BY_KEY[`${distritoId}-${zonaId}`] ?? fallback;
}

const fmt = (n: number | undefined | null) => Number(n ?? 0).toLocaleString("es-BO");
const fmtM3 = (litros: number | undefined | null) => `${fmt(Math.round(Number(litros ?? 0) / 1000))} m³`;
const keyZona = (d: number, z: number) => `${d}-${z}`;

type OfficialDistrictFeature = any;
type OfficialDistrictMap = Map<number, OfficialDistrictFeature>;

function utm19sToLatLon(easting: number, northing: number): [number, number] {
  // EPSG:32719 / WGS 84 UTM Zone 19S -> EPSG:4326.
  // El GeoJSON del repositorio viene acompañado por .prj WGS_1984_UTM_Zone_19S.
  const a = 6378137;
  const f = 1 / 298.257223563;
  const e2 = f * (2 - f);
  const ep2 = e2 / (1 - e2);
  const k0 = 0.9996;
  const x = easting - 500000;
  const y = northing - 10000000;
  const lonOrigin = -69; // zona 19: (19 - 1) * 6 - 180 + 3
  const m = y / k0;
  const mu = m / (a * (1 - e2 / 4 - (3 * e2 ** 2) / 64 - (5 * e2 ** 3) / 256));
  const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
  const j1 = (3 * e1) / 2 - (27 * e1 ** 3) / 32;
  const j2 = (21 * e1 ** 2) / 16 - (55 * e1 ** 4) / 32;
  const j3 = (151 * e1 ** 3) / 96;
  const j4 = (1097 * e1 ** 4) / 512;
  const fp = mu + j1 * Math.sin(2 * mu) + j2 * Math.sin(4 * mu) + j3 * Math.sin(6 * mu) + j4 * Math.sin(8 * mu);
  const sinfp = Math.sin(fp);
  const cosfp = Math.cos(fp);
  const tanfp = Math.tan(fp);
  const c1 = ep2 * cosfp ** 2;
  const t1 = tanfp ** 2;
  const n1 = a / Math.sqrt(1 - e2 * sinfp ** 2);
  const r1 = (a * (1 - e2)) / (1 - e2 * sinfp ** 2) ** 1.5;
  const d = x / (n1 * k0);
  const lat = fp - (n1 * tanfp / r1) *
    (d ** 2 / 2 - ((5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * ep2) * d ** 4) / 24 +
      ((61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * ep2 - 3 * c1 ** 2) * d ** 6) / 720);
  const lon = (
    (d - ((1 + 2 * t1 + c1) * d ** 3) / 6 +
      ((5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * ep2 + 24 * t1 ** 2) * d ** 5) / 120) / cosfp
  );
  return [(lat * 180) / Math.PI, lonOrigin + (lon * 180) / Math.PI];
}

function normalizeCoordPair(pair: any): [number, number] {
  const a = Number(pair?.[0]);
  const b = Number(pair?.[1]);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return [0, 0];
  if (Math.abs(a) > 180 || Math.abs(b) > 90) {
    const [lat, lon] = utm19sToLatLon(a, b);
    return [lon, lat];
  }
  return [a, b];
}

function normalizeGeometryCoords(coords: any): any {
  if (!Array.isArray(coords)) return coords;
  if (typeof coords[0] === "number" && typeof coords[1] === "number") return normalizeCoordPair(coords);
  return coords.map((c) => normalizeGeometryCoords(c));
}

function findFirstPair(coords: any): [number, number] | null {
  if (!Array.isArray(coords)) return null;
  if (typeof coords[0] === "number" && typeof coords[1] === "number") return [Number(coords[0]), Number(coords[1])];
  for (const c of coords) {
    const found = findFirstPair(c);
    if (found) return found;
  }
  return null;
}

function inferDistrictId(props: Record<string, any>, fallback: number): number {
  const entries = Object.entries(props ?? {});
  const preferred = entries.find(([k, v]) => /distr/i.test(k) && Number(v) >= 1 && Number(v) <= 20);
  if (preferred) return Number(preferred[1]);
  const text = entries.map(([, v]) => String(v ?? "")).join(" ");
  const match = text.match(/(?:distrito|dist\.?|d-)\s*(\d{1,2})/i) || text.match(/(1[0-5]|[1-9])/);
  if (match) return Number(match[1]);
  return fallback;
}

function inferDistrictFromKnownAnchors(geometry: any): number | null {
  const counts = new Map<number, number>();
  Object.values(OFFICIAL_ZONE_BY_ID).forEach((anchor) => {
    if (pointInGeometry(anchor.lat, anchor.lon, geometry)) {
      counts.set(anchor.distrito, (counts.get(anchor.distrito) ?? 0) + 1);
    }
  });
  let best: number | null = null;
  let score = 0;
  counts.forEach((count, district) => {
    if (count > score) {
      best = district;
      score = count;
    }
  });
  return best;
}

function normalizeOfficialDistrictGeojson(raw: any): any {
  if (!raw?.features) return null;
  const features = raw.features.map((feature: any, index: number) => {
    const props = feature.properties ?? {};
    const first = findFirstPair(feature.geometry?.coordinates);
    const looksUtm = first ? Math.abs(first[0]) > 180 || Math.abs(first[1]) > 90 : false;
    const geometry = { ...feature.geometry, coordinates: normalizeGeometryCoords(feature.geometry?.coordinates) };
    const distrito_id = inferDistrictFromKnownAnchors(geometry) ?? inferDistrictId(props, index + 1);
    return {
      ...feature,
      properties: {
        ...props,
        distrito_id,
        fuente: "ciudatoslab/20-distritos-en-cochabamba",
        proyeccion_original: looksUtm ? "WGS_1984_UTM_Zone_19S" : "EPSG:4326",
      },
      geometry,
    };
  });
  return { type: "FeatureCollection" as const, features };
}

function flattenRings(geometry: any): Array<Array<[number, number]>> {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return (geometry.coordinates ?? []) as Array<Array<[number, number]>>;
  if (geometry.type === "MultiPolygon") return (geometry.coordinates ?? []).flat() as Array<Array<[number, number]>>;
  return [];
}

function boundsOfGeometry(geometry: any) {
  const rings = flattenRings(geometry);
  let minLat = Infinity;
  let maxLat = -Infinity;
  let minLon = Infinity;
  let maxLon = -Infinity;
  rings.forEach((ring) => ring.forEach(([lon, lat]) => {
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      minLon = Math.min(minLon, lon);
      maxLon = Math.max(maxLon, lon);
    }
  }));
  if (!Number.isFinite(minLat)) return null;
  return { minLat, maxLat, minLon, maxLon, centerLat: (minLat + maxLat) / 2, centerLon: (minLon + maxLon) / 2 };
}

function pointInRing(lat: number, lon: number, ring: Array<[number, number]>): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / ((yj - yi) || 1e-12) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function pointInGeometry(lat: number, lon: number, geometry: any): boolean {
  const rings = flattenRings(geometry);
  if (!rings.length) return false;
  // Primer anillo como contorno. Los huecos no son críticos para el nivel de demo.
  return rings.some((ring) => pointInRing(lat, lon, ring));
}

function isInsideOfficialCercado(lat: number, lon: number, _geojson: any | null): boolean {
  // Para pintar datos se usa el anillo conservador propio de la práctica.
  // El GeoJSON/WMS municipal se mantiene como capa visual, pero no debe borrar
  // datos correctos por diferencias de proyección, escala o fuente.
  if (!insideStrictCercadoBounds(lat, lon)) return false;
  return pointInRing(lat, lon, CERCADO_FALLBACK_RING.map(([la, lo]) => [lo, la] as [number, number]));
}

function districtHoleRingsForMask(geojson: any | null): Array<Array<[number, number]>> {
  if (!geojson?.features?.length) {
    return [CERCADO_FALLBACK_RING];
  }
  const holes: Array<Array<[number, number]>> = [];
  geojson.features.forEach((feature: any) => {
    const geometry = feature.geometry;
    if (!geometry) return;
    if (geometry.type === "Polygon") {
      const ring = geometry.coordinates?.[0];
      if (Array.isArray(ring) && ring.length >= 3) holes.push(ring.map(([lon, lat]: [number, number]) => [lat, lon]));
    }
    if (geometry.type === "MultiPolygon") {
      (geometry.coordinates ?? []).forEach((poly: any) => {
        const ring = poly?.[0];
        if (Array.isArray(ring) && ring.length >= 3) holes.push(ring.map(([lon, lat]: [number, number]) => [lat, lon]));
      });
    }
  });
  return holes.length ? holes : [CERCADO_FALLBACK_RING];
}

function pointForDistrict(feature: OfficialDistrictFeature | undefined, seed: string, fallback: [number, number]): [number, number] {
  const bounds = feature ? boundsOfGeometry(feature.geometry) : null;
  if (!bounds) return fallback;
  const h = hashText(seed);
  for (let i = 0; i < 24; i += 1) {
    const a = ((h + i * 37) % 1000) / 1000;
    const b = ((Math.floor(h / 997) + i * 53) % 1000) / 1000;
    const lat = bounds.minLat + (bounds.maxLat - bounds.minLat) * (0.18 + a * 0.64);
    const lon = bounds.minLon + (bounds.maxLon - bounds.minLon) * (0.18 + b * 0.64);
    if (pointInGeometry(lat, lon, feature.geometry)) return [lat, lon];
  }
  return [bounds.centerLat, bounds.centerLon];
}

function buildOfficialDistrictMap(geojson: any): OfficialDistrictMap {
  const map: OfficialDistrictMap = new Map();
  (geojson?.features ?? []).forEach((feature: any, index: number) => {
    const id = Number(feature.properties?.distrito_id ?? index + 1);
    if (Number.isFinite(id)) map.set(id, feature);
  });
  return map;
}

type OfficialZoneInfo = {
  distrito: number;
  zonaId: number;
  zona: string;
  comuna: string;
  lat: number;
  lon: number;
};

// Fuente territorial usada para corregir la visualización:
// Cochabamba tiene 6 comunas, 15 distritos y las zonas/subdistritos oficiales se listan por distrito.
// El Excel de la práctica trae 54 filas porque repite algunas zonas para distribución de medidores;
// esta tabla normaliza la ubicación visual para que las burbujas caigan en el distrito municipal correcto.
const OFFICIAL_ZONE_BY_ID: Record<number, OfficialZoneInfo> = {
  1: { distrito: 2, zonaId: 1, zona: "MAYORAZGO", comuna: "TUNARI", lat: -17.3890, lon: -66.1780 },
  2: { distrito: 12, zonaId: 2, zona: "SARCO", comuna: "ADELA ZAMUDIO", lat: -17.3930, lon: -66.1730 },
  3: { distrito: 12, zonaId: 3, zona: "CALA CALA", comuna: "ADELA ZAMUDIO", lat: -17.3890, lon: -66.1670 },
  4: { distrito: 12, zonaId: 4, zona: "QUERU QUERU", comuna: "ADELA ZAMUDIO", lat: -17.3870, lon: -66.1590 },
  5: { distrito: 12, zonaId: 5, zona: "TUPURAYA", comuna: "ADELA ZAMUDIO", lat: -17.3990, lon: -66.1590 },
  6: { distrito: 12, zonaId: 6, zona: "HIPODROMO", comuna: "ADELA ZAMUDIO", lat: -17.4030, lon: -66.1690 },
  7: { distrito: 10, zonaId: 7, zona: "NOROESTE", comuna: "ADELA ZAMUDIO", lat: -17.3980, lon: -66.1590 },
  8: { distrito: 10, zonaId: 8, zona: "NORESTE", comuna: "ADELA ZAMUDIO", lat: -17.3980, lon: -66.1490 },
  9: { distrito: 11, zonaId: 9, zona: "MUYURINA", comuna: "ADELA ZAMUDIO", lat: -17.4080, lon: -66.1380 },
  10: { distrito: 4, zonaId: 10, zona: "LA CHIMBA", comuna: "MOLLE", lat: -17.4160, lon: -66.1800 },
  11: { distrito: 10, zonaId: 11, zona: "SUDOESTE", comuna: "ADELA ZAMUDIO", lat: -17.4100, lon: -66.1610 },
  12: { distrito: 10, zonaId: 12, zona: "SUDESTE", comuna: "ADELA ZAMUDIO", lat: -17.4100, lon: -66.1490 },
  13: { distrito: 11, zonaId: 13, zona: "LAS CUADRAS", comuna: "ADELA ZAMUDIO", lat: -17.4140, lon: -66.1440 },
  14: { distrito: 5, zonaId: 14, zona: "LA MAICA", comuna: "ALEJO CALATAYUD", lat: -17.4330, lon: -66.1700 },
  15: { distrito: 5, zonaId: 15, zona: "JAIHUAYCO", comuna: "ALEJO CALATAYUD", lat: -17.4270, lon: -66.1580 },
  16: { distrito: 6, zonaId: 16, zona: "ALALAY NORTE", comuna: "VALLE HERMOSO", lat: -17.4130, lon: -66.1450 },
  17: { distrito: 5, zonaId: 17, zona: "LACMA", comuna: "ALEJO CALATAYUD", lat: -17.4370, lon: -66.1520 },
  18: { distrito: 5, zonaId: 18, zona: "TICTI", comuna: "ALEJO CALATAYUD", lat: -17.4340, lon: -66.0990 },
  19: { distrito: 7, zonaId: 19, zona: "ALALAY SUD", comuna: "VALLE HERMOSO", lat: -17.4220, lon: -66.1330 },
  20: { distrito: 5, zonaId: 20, zona: "VALLE HERMOSO", comuna: "ALEJO CALATAYUD", lat: -17.4400, lon: -66.1070 },
  21: { distrito: 3, zonaId: 21, zona: "SARCOBAMBA", comuna: "MOLLE", lat: -17.3910, lon: -66.1940 },
  22: { distrito: 2, zonaId: 22, zona: "CONDEBAMBA", comuna: "TUNARI", lat: -17.3730, lon: -66.1800 },
  23: { distrito: 2, zonaId: 23, zona: "TEMPORAL PAMPA", comuna: "TUNARI", lat: -17.3770, lon: -66.1680 },
  24: { distrito: 2, zonaId: 24, zona: "QUERU QUERU ALTO", comuna: "TUNARI", lat: -17.3830, lon: -66.1620 },
  25: { distrito: 1, zonaId: 25, zona: "ARANJUEZ ALTO", comuna: "TUNARI", lat: -17.3900, lon: -66.1240 },
  26: { distrito: 1, zonaId: 26, zona: "MESADILLA", comuna: "TUNARI", lat: -17.3800, lon: -66.1300 },
  27: { distrito: 4, zonaId: 27, zona: "VILLA BUSCH", comuna: "MOLLE", lat: -17.4080, lon: -66.1900 },
  28: { distrito: 4, zonaId: 28, zona: "COÑA COÑA", comuna: "MOLLE", lat: -17.4180, lon: -66.1960 },
  29: { distrito: 9, zonaId: 29, zona: "TAMBORADA PUKARITA", comuna: "ITOCTA", lat: -17.4640, lon: -66.1910 },
  30: { distrito: 9, zonaId: 30, zona: "1° DE MAYO", comuna: "ITOCTA", lat: -17.4720, lon: -66.2050 },
  31: { distrito: 9, zonaId: 31, zona: "PUKARA GRANDE NORTE", comuna: "ITOCTA", lat: -17.4600, lon: -66.2190 },
  32: { distrito: 15, zonaId: 32, zona: "VALLE HERMOSO OESTE", comuna: "ITOCTA", lat: -17.4600, lon: -66.1390 },
  33: { distrito: 15, zonaId: 33, zona: "KHARA KHARA ARRUMANI", comuna: "ITOCTA", lat: -17.4740, lon: -66.1410 },
  34: { distrito: 8, zonaId: 34, zona: "USPHA USPHA", comuna: "ALEJO CALATAYUD", lat: -17.4480, lon: -66.1110 },
  35: { distrito: 9, zonaId: 35, zona: "PUKARA GRANDE SUR", comuna: "ITOCTA", lat: -17.4800, lon: -66.1970 },
  36: { distrito: 9, zonaId: 36, zona: "PUKARA GRANDE OESTE", comuna: "ITOCTA", lat: -17.4640, lon: -66.2290 },
  37: { distrito: 3, zonaId: 37, zona: "CHIQUICOLLO", comuna: "MOLLE", lat: -17.4050, lon: -66.1840 },
};

function officialInfoForZone(p: { zona_id: number; zona?: string; distrito_id?: number; centro_lat?: number; centro_lon?: number; sub_alcaldia?: string }): OfficialZoneInfo {
  // IMPORTANTE:
  // No se debe corregir por zona_id solamente, porque el Excel reutiliza algunos zona_id
  // en distintos distritos (por ejemplo 16, 24, 27, 32, 35). Si se remapea solo por zona_id,
  // una zona del Distrito 1 puede terminar dibujándose en el Distrito 2 o 12.
  // Para defensa, la fuente de verdad del poblamiento es el registro compuesto:
  // distrito_id + zona_id + nombre de zona del Excel/seeder.
  const distrito = Number(p.distrito_id ?? 0);
  const zonaId = Number(p.zona_id ?? 0);
  const lat = Number(p.centro_lat ?? CENTRO_CBB[0]);
  const lon = Number(p.centro_lon ?? CENTRO_CBB[1]);
  return {
    distrito,
    zonaId,
    zona: String(p.zona ?? "SIN ZONA").toUpperCase(),
    comuna: String(p.sub_alcaldia ?? ""),
    lat: Number.isFinite(lat) ? lat : CENTRO_CBB[0],
    lon: Number.isFinite(lon) ? lon : CENTRO_CBB[1],
  };
}


function colorEstado(estado: string): string {
  const e = (estado || "").toUpperCase();
  if (e === "ACTIVO") return "#0ea55b";
  if (e === "INACTIVO") return "#f59e0b";
  if (e === "FUERA_SERVICIO") return "#ef4444";
  if (e === "REEMPLAZADO") return "#8b5cf6";
  if (e === "DAÑADO") return "#f97316";
  if (e === "RETIRADO") return "#64748b";
  return "#475569";
}

function metricaZona(p: any, metrica: MetricaMapa): number {
  if (metrica === "consumo") return Number(p.consumo_litros ?? 0) / 1000;
  if (metrica === "fallas") return Number(p.fuera_servicio ?? 0) + Number(p.historicos ?? 0);
  if (metrica === "activos") return Number(p.activos ?? 0);
  return Number(p.medidores ?? p.medidores_ref ?? 0);
}

function colorZona(valor: number, metrica: MetricaMapa): string {
  const limits = metrica === "consumo" ? [500, 1200, 2500, 4200] : metrica === "fallas" ? [40, 120, 300, 600] : [600, 1200, 2200, 3600];
  if (valor <= 0) return "#dbeafe";
  if (valor < limits[0]) return "#bfdbfe";
  if (valor < limits[1]) return "#60a5fa";
  if (valor < limits[2]) return "#2563eb";
  if (valor < limits[3]) return "#1e40af";
  return "#0f172a";
}

function labelMetrica(metrica: MetricaMapa) {
  if (metrica === "consumo") return "consumo m³";
  if (metrica === "fallas") return "fallas / históricos";
  if (metrica === "activos") return "medidores activos";
  return "medidores totales";
}

function iconPunto(color: string): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="width:13px;height:13px;border-radius:9999px;background:${color};border:2px solid #fff;box-shadow:0 1px 5px rgba(15,23,42,.45)"></div>`,
    iconSize: [13, 13],
    iconAnchor: [6.5, 6.5],
  });
}

function hashText(value: string): number {
  let h = 2166136261;
  for (let i = 0; i < value.length; i += 1) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function visualCoordForMedidor(m: MedidorApi, zoneLookup: Map<string, any>): [number, number] {
  // Después de repair_geo.py, Cassandra ya tiene coordenadas corregidas.
  // Usamos esas coordenadas reales del dato, no un centroide visual del frontend.
  const lat = Number(m.latitud);
  const lon = Number(m.longitud);
  const zone = zoneLookup.get(keyZona(Number(m.distrito_id), Number(m.zona_id)));
  if (Number.isFinite(lat) && Number.isFinite(lon) && insideStrictCercadoBounds(lat, lon)) return [lat, lon];
  return [Number(zone?.centro_lat ?? safeCenterForZone(Number(m.distrito_id), Number(m.zona_id))[0]), Number(zone?.centro_lon ?? safeCenterForZone(Number(m.distrito_id), Number(m.zona_id))[1])];
}

function displayDistrictForMedidor(m: MedidorApi, zoneLookup: Map<string, any>): number {
  const zone = zoneLookup.get(keyZona(Number(m.distrito_id), Number(m.zona_id)));
  return Number(zone?.display_distrito_id ?? m.distrito_id);
}

function displayZoneForMedidor(m: MedidorApi, zoneLookup: Map<string, any>): number {
  const zone = zoneLookup.get(keyZona(Number(m.distrito_id), Number(m.zona_id)));
  return Number(zone?.display_zona_id ?? m.zona_id);
}

function cx(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

function MetricCard({ icon, label, value, hint, tone = "blue" }: { icon?: JSX.Element; label: string; value: string | number; hint?: string; tone?: "blue" | "cyan" | "red" | "slate" }) {
  const tones = {
    blue: "from-blue-50 to-white text-blue-700 ring-blue-100",
    cyan: "from-cyan-50 to-white text-cyan-700 ring-cyan-100",
    red: "from-red-50 to-white text-red-700 ring-red-100",
    slate: "from-slate-50 to-white text-slate-700 ring-slate-100",
  };
  return (
    <div className={cx("rounded-2xl bg-gradient-to-br p-4 shadow-sm ring-1", tones[tone])}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] font-black uppercase tracking-[0.16em] text-slate-500">{label}</div>
          <div className="mt-2 text-2xl font-black text-slate-950">{value}</div>
        </div>
        {icon && <div className="rounded-xl bg-white/100 p-2 shadow-sm">{icon}</div>}
      </div>
      {hint && <div className="mt-2 text-xs font-medium text-slate-500">{hint}</div>}
    </div>
  );
}

function SelectBox({ label, children }: { label: string; children: JSX.Element }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[10px] font-black uppercase tracking-[0.16em] text-slate-500">{label}</span>
      {children}
    </label>
  );
}

function ClusterMedidores({ data, visible, zoneLookup }: { data: MedidorApi[]; visible: boolean; zoneLookup: Map<string, any> }) {
  const map = useMap();

  useEffect(() => {
    if (!visible) return;
    const LAny = L as any;
    const cluster = LAny.markerClusterGroup({
      maxClusterRadius: 55,
      chunkedLoading: true,
      iconCreateFunction: (c: any) => {
        const count = c.getChildCount();
        return L.divIcon({
          className: "",
          html: `<div style="height:42px;width:42px;border-radius:9999px;background:linear-gradient(135deg,#0369a1,#0e7490);display:flex;align-items:center;justify-content:center;color:white;font-weight:900;border:2px solid white;box-shadow:0 8px 24px rgba(15,23,42,.38)">${count}</div>`,
          iconSize: [42, 42],
          iconAnchor: [21, 21],
        });
      },
    });

    data.forEach((m) => {
      const [vLat, vLon] = visualCoordForMedidor(m, zoneLookup);
      if (!vLat || !vLon) return;
      const z = zoneLookup.get(keyZona(Number(m.distrito_id), Number(m.zona_id)));
      const displayDistrito = Number(z?.display_distrito_id ?? m.distrito_id);
      const displayZona = Number(z?.display_zona_id ?? m.zona_id);
      const displayNombre = String(z?.zona ?? "Zona");
      const registroBase = `${m.distrito_id}/${m.zona_id}`;
      const color = colorEstado(m.estado);
      const marker = L.marker([vLat, vLon], { icon: iconPunto(color) });
      marker.bindPopup(`
        <div style="font-family:Inter,ui-sans-serif,system-ui;min-width:260px">
          <div style="font-size:14px;font-weight:900;color:#0f172a;margin-bottom:8px">Medidor ${m.estado || "SIN_ESTADO"}</div>
          <div style="font-size:12px;line-height:1.7;color:#334155">
            <b>Contrato:</b> ${m.numero_contrato ?? "—"}<br/>
            <b>MAC:</b> ${m.mac ?? "—"}<br/>
            <b>Serie:</b> ${m.numero_serie ?? "—"}<br/>
            <b>Tarifa:</b> ${m.categoria_tarifa ?? "—"}<br/>
            <b>Zona municipal:</b> ${displayNombre}<br/>
            <b>Distrito municipal:</b> ${displayDistrito} · <b>Zona/Subdistrito:</b> ${displayZona}<br/>
            <span style="color:#64748b"><b>Registro base Excel:</b> D${registroBase}</span><br/>
            <b>Gateway:</b> ${m.gateway_id ?? "—"}<br/>
            <b>Ubicación visual:</b> ${vLat.toFixed(5)}, ${vLon.toFixed(5)}<br/>
            <b>Instalación:</b> ${m.fecha_instalacion ?? "—"}<br/>
            <b>Motivo:</b> ${m.motivo_estado ?? "—"}
          </div>
        </div>
      `);
      cluster.addLayer(marker);
    });

    map.addLayer(cluster);
    return () => {
      map.removeLayer(cluster);
    };
  }, [data, map, visible, zoneLookup]);

  return null;
}

function HeatLayer({ points, visible }: { points: Array<[number, number, number]>; visible: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!visible || points.length === 0) return;
    const LAny = L as any;
    const heat = LAny.heatLayer(points, {
      radius: 32,
      blur: 28,
      maxZoom: 17,
      minOpacity: 0.35,
      gradient: { 0.2: "#93c5fd", 0.45: "#2563eb", 0.7: "#f59e0b", 1.0: "#ef4444" },
    });
    heat.addTo(map);
    return () => {
      map.removeLayer(heat);
    };
  }, [map, points, visible]);
  return null;
}

function CercadoMaskLayer({ data, visible }: { data: any | null; visible: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!visible) return;
    if (!(map as any).getPane("cercado-mask")) {
      const pane = (map as any).createPane("cercado-mask");
      pane.style.zIndex = "330";
      pane.style.pointerEvents = "none";
    }
    const outer: Array<[number, number]> = [[-85, -180], [-85, 180], [85, 180], [85, -180], [-85, -180]];
    const holes = districtHoleRingsForMask(data);
    const mask = L.polygon([outer, ...holes], {
      pane: "cercado-mask",
      interactive: false,
      stroke: false,
      fillColor: "#e5e7eb",
      fillOpacity: 0.72,
      fillRule: "evenodd",
    } as any);
    mask.addTo(map);
    return () => {
      map.removeLayer(mask);
    };
  }, [map, data, visible]);
  return null;
}

function OfficialDistrictGeojsonLayer({ data, visible, selectedDistrict }: { data: any | null; visible: boolean; selectedDistrict: number | "TODOS" }) {
  if (!visible || !data?.features?.length) return null;
  return (
    <GeoJSON
      key={`official-districts-${selectedDistrict}-${data.features.length}`}
      data={data}
      style={(feature: any) => {
        const d = Number(feature?.properties?.distrito_id ?? 0);
        const active = selectedDistrict !== "TODOS" && d === selectedDistrict;
        return {
          color: active ? "#f97316" : "#db2777",
          weight: active ? 3.2 : 1.8,
          fillColor: "#2563eb",
          fillOpacity: active ? 0.12 : 0.04,
          opacity: 0.92,
        };
      }}
      onEachFeature={(feature: any, layer: L.Layer) => {
        const p = feature.properties ?? {};
        (layer as any).bindTooltip(
          `<b>Distrito ${p.distrito_id ?? "—"}</b><br/>Capa GeoJSON vectorial<br/><span style="color:#64748b">Fuente: ciudatoslab/20-distritos-en-cochabamba</span>`,
          { sticky: true }
        );
      }}
    />
  );
}

function OfficialWmsLayers({
  distritos,
  comunas,
  subdistritos,
  cercado,
  manzanas,
  areaUrbana,
}: {
  distritos: boolean;
  comunas: boolean;
  subdistritos: boolean;
  cercado: boolean;
  manzanas: boolean;
  areaUrbana: boolean;
}) {
  const map = useMap();
  useEffect(() => {
    const layers: L.Layer[] = [];
    const add = (layersName: string, opacity: number, zIndex: number) => {
      const layer = L.tileLayer.wms(WMS_BASE, {
        layers: layersName,
        format: "image/png",
        transparent: true,
        version: "1.3.0",
        tiled: true,
        opacity,
        attribution: "Mapa Digital Cochabamba",
      } as any);
      (layer as any).setZIndex?.(zIndex);
      layer.addTo(map);
      layers.push(layer);
    };
    if (areaUrbana) add("tileset_area_urbana19_20170513143014", 0.34, 210);
    if (manzanas) add("tileset_manzanas19_20170417110403", 0.50, 215);
    if (comunas) add("tileset_comunas19", 0.48, 220);
    if (distritos) add("tileset_distritos19_20170513142907", 0.78, 230);
    if (subdistritos) add("tileset_subdistritos19_20170513142942", 0.58, 235);
    if (cercado) add("tileset_cercado19_20170418193906", 0.90, 240);
    return () => {
      layers.forEach((layer) => map.removeLayer(layer));
    };
  }, [map, distritos, comunas, subdistritos, cercado, manzanas, areaUrbana]);
  return null;
}


function buildDistrictGuideGeojson(zoneGeojson: any, selectedDistrict: number | "TODOS") {
  const groups = new Map<number, any[]>();
  (zoneGeojson?.features ?? []).forEach((feature: any) => {
    const p = feature.properties ?? {};
    const d = Number(p.distrito_id);
    if (!Number.isFinite(d)) return;
    if (selectedDistrict !== "TODOS" && d !== selectedDistrict) return;
    if (!groups.has(d)) groups.set(d, []);
    groups.get(d)!.push(p);
  });
  const features: any[] = [];
  groups.forEach((items, distritoId) => {
    const lats = items.map((x) => Number(x.centro_lat)).filter(Number.isFinite);
    const lons = items.map((x) => Number(x.centro_lon)).filter(Number.isFinite);
    if (!lats.length || !lons.length) return;
    const minLat = Math.min(...lats) - 0.010;
    const maxLat = Math.max(...lats) + 0.010;
    const minLon = Math.min(...lons) - 0.012;
    const maxLon = Math.max(...lons) + 0.012;
    features.push({
      type: "Feature",
      properties: { distrito_id: distritoId, zonas: items.length },
      geometry: {
        type: "Polygon",
        coordinates: [[[minLon, minLat], [maxLon, minLat], [maxLon, maxLat], [minLon, maxLat], [minLon, minLat]]],
      },
    });
  });
  return { type: "FeatureCollection" as const, features };
}

function DistrictGuideLayer({ zoneGeojson, visible, selectedDistrict }: { zoneGeojson: any; visible: boolean; selectedDistrict: number | "TODOS" }) {
  const data = useMemo(() => buildDistrictGuideGeojson(zoneGeojson, selectedDistrict), [zoneGeojson, selectedDistrict]);
  if (!visible || !data.features.length) return null;
  return (
    <GeoJSON
      key={`district-guide-${selectedDistrict}-${data.features.length}`}
      data={data}
      style={(feature: any) => ({
        color: selectedDistrict !== "TODOS" ? "#f97316" : "#0f766e",
        weight: selectedDistrict !== "TODOS" ? 3.2 : 2.1,
        fillOpacity: 0,
        opacity: 0.95,
        dashArray: selectedDistrict !== "TODOS" ? "" : "8 6",
      })}
      onEachFeature={(feature: any, layer: L.Layer) => {
        const p = feature.properties ?? {};
        (layer as any).bindTooltip(
          `<b>Distrito ${p.distrito_id}</b><br/>Guía SEMAPA persistente<br/><span style="color:#64748b">No desaparece al hacer zoom</span>`,
          { sticky: true }
        );
      }}
    />
  );
}

function FitToSelection({ selectedZone }: { selectedZone: any | null }) {
  const map = useMap();
  useEffect(() => {
    if (!selectedZone?.centro_lat || !selectedZone?.centro_lon) return;
    map.flyTo([Number(selectedZone.centro_lat), Number(selectedZone.centro_lon)], 14, { duration: 0.7 });
  }, [map, selectedZone]);
  return null;
}

export default function Mapa() {
  const [estado, setEstado] = useState<EstadoFiltro>("TODOS");
  const [categoria, setCategoria] = useState<CategoriaFiltro>("TODAS");
  const [distrito, setDistrito] = useState<number | "TODOS">("TODOS");
  const [zonaId, setZonaId] = useState<number | "TODAS">("TODAS");
  const [gatewayId, setGatewayId] = useState<number | "TODOS">("TODOS");
  const [busqueda, setBusqueda] = useState("");
  const [capa, setCapa] = useState<CapaAnalitica>("burbujas");
  const [metrica, setMetrica] = useState<MetricaMapa>("consumo");
  const [sampleLimit, setSampleLimit] = useState(4000);
  const [showLocalZonas, setShowLocalZonas] = useState(false);
  const [showDistritoGuia, setShowDistritoGuia] = useState(false);
  const [showGeoJsonDistritos, setShowGeoJsonDistritos] = useState(false);
  const [showDistritos, setShowDistritos] = useState(true);
  const [showComunas, setShowComunas] = useState(false);
  const [showSubdistritos, setShowSubdistritos] = useState(false);
  const [showCercado, setShowCercado] = useState(true);
  const [showGateways, setShowGateways] = useState(false);
  const [showManzanas, setShowManzanas] = useState(false);
  const [showAreaUrbana, setShowAreaUrbana] = useState(false);
  const [showOutsideGray, setShowOutsideGray] = useState(true);
  const [panelCapasOpen, setPanelCapasOpen] = useState(false);
  const [panelAnalisisOpen, setPanelAnalisisOpen] = useState(true);
  const [selectedZone, setSelectedZone] = useState<any>(null);
  const [officialDistricts, setOfficialDistricts] = useState<any | null>(null);
  const [officialDistrictsStatus, setOfficialDistrictsStatus] = useState<"cargando" | "ok" | "error">("cargando");

  useEffect(() => {
    let cancelled = false;
    const loadOfficialDistricts = async () => {
      setOfficialDistrictsStatus("cargando");
      const urls = [OFFICIAL_DISTRICTS_URL, OFFICIAL_DISTRICTS_RAW_URL];
      for (const url of urls) {
        try {
          const response = await fetch(url, { cache: "force-cache" });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const raw = await response.json();
          const normalized = normalizeOfficialDistrictGeojson(raw);
          if (!normalized?.features?.length) throw new Error("GeoJSON vacío");
          if (!cancelled) {
            setOfficialDistricts(normalized);
            setOfficialDistrictsStatus("ok");
          }
          return;
        } catch (error) {
          console.warn("No se pudo cargar GeoJSON oficial desde", url, error);
        }
      }
      if (!cancelled) setOfficialDistrictsStatus("error");
    };
    loadOfficialDistricts();
    return () => { cancelled = true; };
  }, []);

  const officialDistrictMap = useMemo(() => buildOfficialDistrictMap(officialDistricts), [officialDistricts]);

  const resumen = useQuery<ResumenMapaApi>({
    queryKey: ["mapa-resumen"],
    queryFn: async () => (await api.get("/mapa/resumen")).data,
    retry: 1,
  });
  const zonas = useQuery<ZonaApi[]>({
    queryKey: ["mapa-zonas", estado, categoria, distrito, zonaId, gatewayId],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (estado !== "TODOS") params.set("estado", estado);
      if (categoria !== "TODAS") params.set("categoria", categoria);
      if (distrito !== "TODOS") params.set("distrito_id", String(distrito));
      if (zonaId !== "TODAS") params.set("zona_id", String(zonaId));
      if (gatewayId !== "TODOS") params.set("gateway_id", String(gatewayId));
      const qs = params.toString();
      return (await api.get(`/mapa/zonas${qs ? `?${qs}` : ""}`)).data;
    },
    retry: 1,
  });
  const gateways = useQuery<GatewayApi[]>({
    queryKey: ["mapa-gateways"],
    queryFn: async () => (await api.get("/mapa/gateways")).data,
    retry: 1,
  });
  const medidores = useQuery<MedidorApi[]>({
    queryKey: ["mapa-medidores-sample", sampleLimit, estado, categoria, distrito, zonaId, gatewayId],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: String(sampleLimit) });
      if (estado !== "TODOS") params.set("estado", estado);
      if (categoria !== "TODAS") params.set("categoria", categoria);
      if (distrito !== "TODOS") params.set("distrito_id", String(distrito));
      if (zonaId !== "TODAS") params.set("zona_id", String(zonaId));
      if (gatewayId !== "TODOS") params.set("gateway_id", String(gatewayId));
      return (await api.get(`/mapa/medidores-sample?${params.toString()}`)).data;
    },
    retry: 1,
  });
  const horasPico = useQuery<HoraPicoApi[]>({
    queryKey: ["horas-pico-mapa"],
    queryFn: async () => (await api.get("/consultas/horas-pico")).data,
    retry: 1,
  });

  const statsByZone = useMemo(() => {
    const map = new Map<string, ZonaApi>();
    (zonas.data ?? []).forEach((z) => map.set(keyZona(z.distrito_id, z.zona_id), z));
    return map;
  }, [zonas.data]);

  const geojson: any = useMemo(() => {
    return {
      ...COCHABAMBA_ZONAS_GEOJSON,
      features: (COCHABAMBA_ZONAS_GEOJSON as any).features.map((feature: any) => {
        const p = feature.properties;
        const apiStats = statsByZone.get(keyZona(p.distrito_id, p.zona_id));
        // Fuente de verdad visual: si la API ya calculó centroides desde Cassandra,
        // usamos esos centros. Si no, usamos el fallback estático del frontend.
        // Para la defensa visual, el centro de burbuja se toma de la referencia segura
        // por distrito+zona. Si Cassandra aún conserva coordenadas antiguas fuera de Cercado,
        // esto evita que las burbujas aparezcan en Sacaba/Tiquipaya/Quillacollo.
        const fallbackCenter = safeCenterForZone(Number(p.distrito_id), Number(p.zona_id), [Number(p.centro_lat ?? CENTRO_CBB[0]), Number(p.centro_lon ?? CENTRO_CBB[1])]);
        const lat = fallbackCenter[0];
        const lon = fallbackCenter[1];
        const size = 0.0028;
        return {
          ...feature,
          properties: {
            ...p,
            ...(apiStats ?? {}),
            raw_distrito_id: p.distrito_id,
            raw_zona_id: p.zona_id,
            raw_zona: apiStats?.zona || p.zona,
            distrito_id: p.distrito_id,
            zona_id: p.zona_id,
            zona: apiStats?.zona || p.zona,
            display_distrito_id: p.distrito_id,
            display_zona_id: p.zona_id,
            display_zona: apiStats?.zona || p.zona,
            medidores: apiStats?.medidores ?? p.medidores_ref ?? 0,
            activos: apiStats?.activos ?? 0,
            fuera_servicio: apiStats?.fuera_servicio ?? 0,
            historicos: apiStats?.historicos ?? 0,
            consumo_litros: apiStats?.consumo_litros ?? 0,
            infraestructuras_base: apiStats?.infraestructuras_base ?? p.infraestructuras_base,
            centro_lat: lat,
            centro_lon: lon,
            fuente_geometria: apiStats?.centro_lat ? "centroide Cassandra reparado" : "centroide local fallback",
            correccion_municipal: false,
          },
          geometry: {
            type: "Polygon",
            coordinates: [[[lon - size, lat - size], [lon + size, lat - size], [lon + size, lat + size], [lon - size, lat + size], [lon - size, lat - size]]],
          },
        };
      }),
    };
  }, [statsByZone]);

  const visualZoneLookup = useMemo(() => {
    const map = new Map<string, any>();
    geojson.features.forEach((feature: any) => map.set(keyZona(feature.properties.raw_distrito_id ?? feature.properties.distrito_id, feature.properties.raw_zona_id ?? feature.properties.zona_id), feature.properties));
    return map;
  }, [geojson]);

  const zonasFiltradasGeojson: any = useMemo(() => {
    return {
      ...geojson,
      features: geojson.features.filter((feature: any) => {
        const p = feature.properties;
        if (distrito !== "TODOS" && Number(p.display_distrito_id ?? p.distrito_id) !== distrito) return false;
        if (zonaId !== "TODAS" && Number(p.display_zona_id ?? p.zona_id) !== zonaId) return false;
        if (gatewayId !== "TODOS" && Number(p.gateway_id) !== gatewayId) return false;
        if (!isInsideOfficialCercado(Number(p.centro_lat), Number(p.centro_lon), officialDistricts)) return false;
        // Cuando se busca un contrato/MAC/serie/UUID, se muestran solo puntos, no burbujas agregadas.
        if (busqueda.trim().length > 0) return false;
        // Si se aplican filtros, no se dibujan zonas/burbujas sin datos coincidentes.
        // Esto evita que queden círculos de otras categorías/estados/distritos.
        if (Number(p.medidores ?? 0) <= 0) return false;
        return true;
      }),
    };
  }, [geojson, distrito, zonaId, gatewayId, estado, categoria, busqueda, officialDistricts]);

  const medidoresFiltrados = useMemo(() => {
    const q = busqueda.trim().toUpperCase();
    return (medidores.data ?? []).filter((m) => {
      if (estado !== "TODOS" && (m.estado || "").toUpperCase() !== estado) return false;
      if (categoria !== "TODAS" && m.categoria_tarifa !== categoria) return false;
      const displayDistrito = displayDistrictForMedidor(m, visualZoneLookup);
      const displayZona = displayZoneForMedidor(m, visualZoneLookup);
      if (distrito !== "TODOS" && displayDistrito !== distrito) return false;
      if (zonaId !== "TODAS" && displayZona !== zonaId) return false;
      if (gatewayId !== "TODOS" && m.gateway_id !== gatewayId) return false;
      const [lat, lon] = visualCoordForMedidor(m, visualZoneLookup);
      if (!isInsideOfficialCercado(lat, lon, officialDistricts)) return false;
      if (q) {
        const hay = [m.mac, m.numero_serie, String(m.numero_contrato), m.medidor_id].some((v) => String(v ?? "").toUpperCase().includes(q));
        if (!hay) return false;
      }
      return true;
    });
  }, [medidores.data, estado, categoria, distrito, zonaId, gatewayId, busqueda, visualZoneLookup, officialDistricts]);

  const distritos = useMemo(() => {
    const ids = new Set<number>();
    geojson.features.forEach((f: any) => ids.add(Number(f.properties.display_distrito_id ?? f.properties.distrito_id)));
    return [...ids].sort((a, b) => a - b);
  }, [geojson]);

  const zonasSelect = useMemo(() => {
    const byKey = new Map<string, any>();
    geojson.features
      .map((f: any) => f.properties)
      .filter((p: any) => distrito === "TODOS" || Number(p.display_distrito_id ?? p.distrito_id) === distrito)
      .forEach((p: any) => byKey.set(`${p.display_distrito_id ?? p.distrito_id}-${p.display_zona_id ?? p.zona_id}`, p));
    return [...byKey.values()].sort((a: any, b: any) => String(a.zona).localeCompare(String(b.zona)));
  }, [geojson, distrito]);

  const gatewayOptions = useMemo(() => [...(gateways.data ?? [])].sort((a, b) => a.gateway_id - b.gateway_id), [gateways.data]);

  const heatPoints = useMemo<Array<[number, number, number]>>(() => {
    if (capa === "puntos") return [];
    if (metrica === "medidores") {
      return medidoresFiltrados.map((m) => {
        const [lat, lon] = visualCoordForMedidor(m, visualZoneLookup);
        return [lat, lon, 0.45] as [number, number, number];
      });
    }
    return zonasFiltradasGeojson.features.map((feature: any) => {
      const p = feature.properties;
      const raw = metricaZona(p, metrica);
      const normalized = Math.max(0.15, Math.min(1, raw / (metrica === "consumo" ? 5000 : 4000)));
      return [Number(p.centro_lat), Number(p.centro_lon), normalized] as [number, number, number];
    });
  }, [capa, metrica, medidoresFiltrados, zonasFiltradasGeojson.features, visualZoneLookup]);

  const zonasOrdenadas = useMemo(() => {
    return [...zonasFiltradasGeojson.features]
      .map((f: any) => f.properties)
      .sort((a: any, b: any) => metricaZona(b, metrica) - metricaZona(a, metrica));
  }, [zonasFiltradasGeojson.features, metrica]);

  const chartZonas = zonasOrdenadas.slice(0, 8).map((z: any) => ({
    name: `D${z.display_distrito_id ?? z.distrito_id} · ${String(z.zona).slice(0, 16)}`,
    valor: Math.round(metricaZona(z, metrica)),
  }));

  const chartHoras = useMemo(() => {
    const raw = horasPico.data ?? [];
    if (raw.length) return raw.map((h) => ({ hora: `${String(h.hora).padStart(2, "0")}:00`, consumo_m3: Math.round(h.consumo_litros / 1000) }));
    return [0, 8, 16].map((h) => ({ hora: `${String(h).padStart(2, "0")}:00`, consumo_m3: 0 }));
  }, [horasPico.data]);

  const estadoData = useMemo(() => Object.entries(resumen.data?.por_estado ?? {}).map(([name, value]) => ({ name, value })), [resumen.data]);

  const styleZona = (feature: any) => {
    const p = feature.properties;
    const value = metricaZona(p, metrica);
    const isSelected = selectedZone && keyZona(selectedZone.display_distrito_id ?? selectedZone.distrito_id, selectedZone.display_zona_id ?? selectedZone.zona_id) === keyZona(p.display_distrito_id ?? p.distrito_id, p.display_zona_id ?? p.zona_id);
    return {
      fillColor: colorZona(value, metrica),
      color: isSelected ? "#f97316" : "#0369a1",
      weight: isSelected ? 3.2 : 1.35,
      fillOpacity: capa === "calor" ? 0.16 : 0.58,
      opacity: 0.94,
    };
  };

  const onEachZona = (feature: any, layer: L.Layer) => {
    const p = feature.properties;
    (layer as any).bindTooltip(
      `<b>${p.zona}</b><br/>Distrito municipal ${p.distrito_id} · Zona/Subdistrito ${p.zona_id}<br/>${p.correccion_municipal ? `<span style="color:#64748b">Base Excel: D${p.raw_distrito_id}/Z${p.raw_zona_id}</span><br/>` : ""}${fmt(p.medidores)} medidores · ${fmtM3(p.consumo_litros)}`,
      { sticky: true }
    );
    layer.on({
      click: () => setSelectedZone(p),
      mouseover: (e: any) => e.target.setStyle({ fillOpacity: 0.78, weight: 2.6 }),
      mouseout: (e: any) => e.target.setStyle(styleZona(feature)),
    });
  };

  const resetFiltros = () => {
    setEstado("TODOS");
    setCategoria("TODAS");
    setDistrito("TODOS");
    setZonaId("TODAS");
    setGatewayId("TODOS");
    setBusqueda("");
    setSelectedZone(null);
  };

  const loading = resumen.isLoading || zonas.isLoading || gateways.isLoading || medidores.isLoading;
  const hayFiltrosActivos = estado !== "TODOS" || categoria !== "TODAS" || distrito !== "TODOS" || zonaId !== "TODAS" || gatewayId !== "TODOS" || busqueda.trim().length > 0;
  const fallas = Number(resumen.data?.fuera_servicio ?? 0) + Number(resumen.data?.historicos ?? 0);
  const consumoTotalM3 = Math.round((zonas.data ?? []).reduce((acc: number, z: any) => acc + Number(z.consumo_litros ?? 0), 0) / 1000);
  const poblacionBeneficiaria = 85000;

  return (
    <div className="space-y-4">
      <section className="relative overflow-hidden rounded-[24px] bg-gradient-to-br from-sky-950 via-blue-900 to-cyan-800 p-5 text-white shadow-xl">
        <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-cyan-300/20 blur-3xl" />
        <div className="absolute -bottom-20 left-20 h-52 w-52 rounded-full bg-blue-300/10 blur-3xl" />
        <div className="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-black uppercase tracking-[0.18em] text-cyan-100 backdrop-blur">
              <MapPinned size={14} /> Módulo de georreferenciación
            </div>
            <h1 className="text-2xl font-black tracking-tight md:text-3xl">Mapa SEMAPA · Cochabamba</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-blue-100">
              Demostración de tu parte: poblamiento masivo solo para el municipio Cercado, distribución por sus 15 distritos/zonas, gateways, estados, coordenadas, mapa de calor, burbujas, filtros y validación visual con capas municipales ocultables. Fuera de Cercado se muestra en gris.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
            <div className="rounded-2xl bg-white/10 p-3 backdrop-blur"><div className="font-black text-white">54</div><div className="text-blue-100">zonas cargadas</div></div>
            <div className="rounded-2xl bg-white/10 p-3 backdrop-blur"><div className="font-black text-white">{officialDistrictsStatus === "ok" ? (officialDistricts?.features?.length ?? 15) : 15}</div><div className="text-blue-100">distritos</div></div>
            <div className="rounded-2xl bg-white/10 p-3 backdrop-blur"><div className="font-black text-white">14</div><div className="text-blue-100">radiobases</div></div>
            <div className="rounded-2xl bg-white/10 p-3 backdrop-blur"><div className="font-black text-white">9</div><div className="text-blue-100">tarifas</div></div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <MetricCard icon={<Waves size={18} />} label="Consumo total" value={`${fmt(consumoTotalM3)} m³`} hint="según lecturas demo" tone="cyan" />
        <MetricCard icon={<Building2 size={18} />} label="Infraestructuras" value={fmt(resumen.data?.infraestructuras ?? 80000)} hint="meta nueva: 80.000" />
        <MetricCard icon={<CircleDot size={18} />} label="Población beneficiaria" value={fmt(poblacionBeneficiaria)} hint="80k naturales + 5k jurídicas" />
        <MetricCard icon={<Waves size={18} />} label="Medidores" value={fmt(resumen.data?.medidores ?? 120000)} hint="meta: 120.000" tone="cyan" />
        <MetricCard icon={<ShieldCheck size={18} />} label="Activos" value={fmt(resumen.data?.activos ?? 0)} hint="reportan normalmente" />
        <MetricCard icon={<Activity size={18} />} label="Fallas / históricos" value={fmt(fallas)} hint="reemplazos, daño, retiro" tone="red" />
        <MetricCard icon={<RadioTower size={18} />} label="Gateways" value={fmt(resumen.data?.gateways_con_medidores ?? 14)} hint="14 radiobases" tone="slate" />
      </div>

      <section className="rounded-[24px] border border-blue-100 bg-white p-4 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-slate-900">
            <SlidersHorizontal className="text-blue-700" size={19} />
            <h2 className="font-black">Filtros de defensa</h2>
            <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-bold text-blue-700">{fmt(medidoresFiltrados.length)} puntos en muestra</span>
          </div>
          <button onClick={resetFiltros} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50">
            <RotateCcw size={14} /> limpiar filtros
          </button>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
          <SelectBox label="Estado">
            <select className="input-pro" value={estado} onChange={(e) => setEstado(e.target.value as EstadoFiltro)}>
              {['TODOS', 'ACTIVO', 'INACTIVO', 'FUERA_SERVICIO', 'REEMPLAZADO', 'DAÑADO', 'RETIRADO'].map((x) => <option key={x}>{x}</option>)}
            </select>
          </SelectBox>
          <SelectBox label="Tarifa">
            <select className="input-pro" value={categoria} onChange={(e) => setCategoria(e.target.value as CategoriaFiltro)}>
              {['TODAS', 'R1', 'R2', 'R3', 'R4', 'C', 'CE', 'I', 'P', 'S'].map((x) => <option key={x}>{x}</option>)}
            </select>
          </SelectBox>
          <SelectBox label="Distrito">
            <select className="input-pro" value={distrito} onChange={(e) => { setDistrito(e.target.value === 'TODOS' ? 'TODOS' : Number(e.target.value)); setZonaId('TODAS'); }}>
              <option value="TODOS">Todos</option>
              {distritos.map((d) => <option key={d} value={d}>Distrito {d}</option>)}
            </select>
          </SelectBox>
          <SelectBox label="Zona">
            <select className="input-pro" value={zonaId} onChange={(e) => setZonaId(e.target.value === 'TODAS' ? 'TODAS' : Number(e.target.value))}>
              <option value="TODAS">Todas</option>
              {zonasSelect.map((z: any) => <option key={`${z.distrito_id}-${z.zona_id}`} value={z.zona_id}>{z.zona}</option>)}
            </select>
          </SelectBox>
          <SelectBox label="Gateway">
            <select className="input-pro" value={gatewayId} onChange={(e) => setGatewayId(e.target.value === 'TODOS' ? 'TODOS' : Number(e.target.value))}>
              <option value="TODOS">Todos</option>
              {gatewayOptions.map((g) => <option key={g.gateway_id} value={g.gateway_id}>GW {g.gateway_id}</option>)}
            </select>
          </SelectBox>
          <SelectBox label="Visualización">
            <select className="input-pro" value={capa} onChange={(e) => setCapa(e.target.value as CapaAnalitica)}>
              <option value="mixto">Mixto</option>
              <option value="calor">Calor</option>
              <option value="burbujas">Burbujas</option>
              <option value="puntos">Puntos</option>
            </select>
          </SelectBox>
          <SelectBox label="Métrica">
            <select className="input-pro" value={metrica} onChange={(e) => setMetrica(e.target.value as MetricaMapa)}>
              <option value="consumo">Consumo</option>
              <option value="medidores">Medidores</option>
              <option value="activos">Activos</option>
              <option value="fallas">Fallas</option>
            </select>
          </SelectBox>
          <SelectBox label="Muestra">
            <select className="input-pro" value={sampleLimit} onChange={(e) => setSampleLimit(Number(e.target.value))}>
              {SAMPLE_OPTIONS.map((n) => <option key={n} value={n}>{fmt(n)}</option>)}
            </select>
          </SelectBox>
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
          <Search size={16} className="text-slate-400" />
          <input
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            className="w-full bg-transparent text-sm outline-none"
            placeholder="Buscar dentro de la muestra por contrato, MAC, serie o UUID del medidor..."
          />
        </div>
      </section>

      <div className="space-y-4">
        <div className="relative h-[82vh] min-h-[760px] overflow-hidden rounded-[28px] border border-blue-100 bg-white shadow-md">
          <MapContainer center={[-17.425, -66.155]} zoom={12.25} zoomSnap={0.25} style={{ height: "100%", width: "100%" }}>
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            />
            <CercadoMaskLayer data={officialDistricts} visible={showOutsideGray} />
            <OfficialWmsLayers distritos={showDistritos} comunas={showComunas} subdistritos={showSubdistritos} cercado={showCercado} manzanas={showManzanas} areaUrbana={showAreaUrbana} />
            <DistrictGuideLayer zoneGeojson={geojson} visible={showDistritoGuia} selectedDistrict={distrito} />
            <OfficialDistrictGeojsonLayer data={officialDistricts} visible={showGeoJsonDistritos} selectedDistrict={distrito} />
            {showLocalZonas && <GeoJSON key={`${zonas.dataUpdatedAt}-${selectedZone?.zona_id ?? 'x'}-${metrica}-${capa}-${distrito}-${zonaId}-${gatewayId}`} data={zonasFiltradasGeojson} style={styleZona} onEachFeature={onEachZona} />}
            <HeatLayer points={heatPoints} visible={capa === "calor" || capa === "mixto"} />
            {capa !== "calor" && zonasFiltradasGeojson.features.map((feature: any) => {
              const p = feature.properties;
              if (!Number.isFinite(Number(p.centro_lat)) || !Number.isFinite(Number(p.centro_lon))) return null;
              const value = metricaZona(p, metrica);
              const radius = Math.max(8, Math.min(34, 7 + Math.sqrt(Math.max(value, 1)) / (metrica === "consumo" ? 2.2 : 3.5)));
              return (
                <CircleMarker
                  key={`${p.distrito_id}-${p.zona_id}`}
                  center={[Number(p.centro_lat), Number(p.centro_lon)]}
                  radius={radius}
                  pathOptions={{ color: "#ffffff", fillColor: colorZona(value, metrica), fillOpacity: 0.76, weight: 2 }}
                  eventHandlers={{ click: () => setSelectedZone(p) }}
                >
                  <Tooltip direction="top" offset={[0, -8]}>{p.zona} · {fmt(Math.round(value))} {labelMetrica(metrica)}</Tooltip>
                  <Popup>
                    <div className="min-w-[220px] text-sm">
                      <div className="font-black text-slate-900">{p.zona}</div>
                      <div className="text-slate-500">Distrito municipal {p.distrito_id} · Zona/Subdistrito {p.zona_id}</div>
                      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                        <b>Medidores</b><span>{fmt(p.medidores)}</span>
                        <b>Activos</b><span>{fmt(p.activos)}</span>
                        <b>Fuera servicio</b><span>{fmt(p.fuera_servicio)}</span>
                        <b>Consumo</b><span>{fmtM3(p.consumo_litros)}</span>
                      </div>
                    </div>
                  </Popup>
                </CircleMarker>
              );
            })}
            <ClusterMedidores data={medidoresFiltrados} visible={capa === "puntos" || capa === "mixto"} zoneLookup={visualZoneLookup} />
            {showGateways && (gateways.data ?? []).filter((g) => insideStrictCercadoBounds(Number(g.latitud), Number(g.longitud)) && (gatewayId === "TODOS" || g.gateway_id === gatewayId)).map((g) => (
              <CircleMarker
                key={g.gateway_id}
                center={[Number(g.latitud), Number(g.longitud)]}
                radius={9}
                pathOptions={{ color: "#0f172a", fillColor: "#06b6d4", fillOpacity: 0.95, weight: 2.5 }}
              >
                <Tooltip direction="top" offset={[0, -4]}>{g.nombre}</Tooltip>
                <Popup>
                  <div className="text-sm">
                    <div className="font-black">{g.nombre}</div>
                    <div>Gateway #{g.gateway_id}</div>
                    <div>{fmt(g.medidores)} medidores</div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
            <FitToSelection selectedZone={selectedZone} />
          </MapContainer>

          <div className="absolute right-4 top-4 z-[1000] flex flex-col items-end gap-2">
            <button
              onClick={() => setPanelCapasOpen((v) => !v)}
              className="inline-flex items-center gap-2 rounded-2xl border border-white/80 bg-white/95 px-4 py-3 text-sm font-black text-slate-800 shadow-xl backdrop-blur hover:bg-blue-50"
            >
              <Layers size={17} className="text-blue-700" /> {panelCapasOpen ? "Ocultar capas" : "Capas"}
            </button>
            {panelCapasOpen && (
              <div className="max-h-[72vh] w-[320px] overflow-y-auto rounded-2xl border border-white/70 bg-white/95 p-4 shadow-xl backdrop-blur">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <div className="text-sm font-black text-slate-900">Capas del mapa</div>
                  <button
                    className="rounded-xl bg-slate-100 px-2 py-1 text-[11px] font-black text-slate-600 hover:bg-slate-200"
                    onClick={() => { setShowDistritoGuia(false); setShowGeoJsonDistritos(false); setShowDistritos(true); setShowComunas(false); setShowSubdistritos(false); setShowCercado(true); setShowManzanas(false); setShowAreaUrbana(false); setShowGateways(false); setShowOutsideGray(true); setShowLocalZonas(false); }}
                  >
                    apagar capas
                  </button>
                </div>
                <div className="mb-3 rounded-xl bg-blue-50 p-2">
                  <div className="mb-2 text-[11px] font-black uppercase tracking-[0.12em] text-blue-900">Visualización</div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      ["burbujas", "Burbujas"],
                      ["calor", "Calor"],
                      ["puntos", "Puntos"],
                      ["mixto", "Mixto"],
                    ].map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setCapa(value as CapaAnalitica)}
                        className={`rounded-lg px-2 py-1.5 text-xs font-black ${capa === value ? "bg-blue-700 text-white" : "bg-white text-slate-700 hover:bg-blue-100"}`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                {[
                  [showOutsideGray, setShowOutsideGray, "Fuera de Cercado en gris"],
                  [showLocalZonas, setShowLocalZonas, "Zonas SEMAPA"],
                  [showGateways, setShowGateways, "Gateways / radiobases"],
                  [showDistritos, setShowDistritos, "Distritos municipales"],
                  [showComunas, setShowComunas, "Comunas"],
                  [showSubdistritos, setShowSubdistritos, "Subdistritos"],
                  [showCercado, setShowCercado, "Límite Cercado"],
                  [showAreaUrbana, setShowAreaUrbana, "Área urbana"],
                  [showManzanas, setShowManzanas, "Manzanas"],
                ].map(([checked, setter, label]) => (
                  <label key={String(label)} className="mb-2 flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-blue-50">
                    <span className="min-w-0">{String(label)}</span>
                    <input type="checkbox" checked={Boolean(checked)} onChange={(e) => (setter as any)(e.target.checked)} />
                  </label>
                ))}
                <div className="mt-2 rounded-xl bg-blue-50 p-2 text-[11px] leading-5 text-blue-900">
                  Prioridad: solo se muestran datos dentro del municipio Cercado. Fuera de Cercado queda en gris y las capas municipales se pueden ocultar.
                </div>
              </div>
            )}
          </div>

          <div className="absolute bottom-4 left-4 z-[1000] rounded-2xl border border-white/100 bg-white/95 p-4 shadow-xl backdrop-blur">
            <div className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-[0.14em] text-slate-700"><Flame size={15} className="text-orange-500" /> Intensidad</div>
            {[
              ['#bfdbfe', 'Bajo'], ['#60a5fa', 'Medio'], ['#2563eb', 'Alto'], ['#1e40af', 'Muy alto'], ['#0f172a', 'Crítico'],
            ].map(([c, l]) => (
              <div key={l} className="mb-1 flex items-center gap-2 text-xs text-slate-600"><span className="h-3 w-6 rounded" style={{ background: c }} />{l}</div>
            ))}
            <hr className="my-2" />
            {[
              ['#0ea55b', 'Activo'], ['#ef4444', 'Fuera servicio'], ['#8b5cf6', 'Reemplazado'], ['#f97316', 'Dañado'], ['#64748b', 'Retirado'],
            ].map(([c, l]) => (
              <div key={l} className="mb-1 flex items-center gap-2 text-xs text-slate-600"><span className="h-3 w-3 rounded-full" style={{ background: c }} />{l}</div>
            ))}
          </div>

          {loading && (
            <div className="absolute inset-0 z-[999] flex items-center justify-center bg-white/50 backdrop-blur-sm">
              <div className="rounded-2xl bg-white px-5 py-4 text-sm font-black shadow-xl">Cargando mapa territorial...</div>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <button onClick={() => setPanelAnalisisOpen((v) => !v)} className="rounded-2xl border border-blue-100 bg-white px-4 py-2 text-sm font-black text-blue-700 shadow-sm hover:bg-blue-50">
            {panelAnalisisOpen ? "Ocultar análisis lateral" : "Mostrar análisis lateral"}
          </button>
        </div>

        {panelAnalisisOpen && <aside className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-4">
          <div className="rounded-[24px] border border-blue-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-slate-900"><CircleDot className="text-blue-700" size={18} /><h2 className="font-black">Detalle geográfico</h2></div>
            {selectedZone ? (
              <div className="space-y-3">
                <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-white p-4 ring-1 ring-blue-100">
                  <div className="text-xs font-black uppercase tracking-[0.16em] text-blue-700">Zona seleccionada</div>
                  <div className="mt-1 text-2xl font-black text-slate-950">{selectedZone.zona}</div>
                  <div className="text-sm text-slate-500">{selectedZone.sub_alcaldia} · Distrito {selectedZone.distrito_id} · Zona {selectedZone.zona_id}</div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <MetricCard label="Medidores" value={fmt(selectedZone.medidores)} />
                  <MetricCard label="Activos" value={fmt(selectedZone.activos)} tone="cyan" />
                  <MetricCard label="Fuera servicio" value={fmt(selectedZone.fuera_servicio)} tone="red" />
                  <MetricCard label="Históricos" value={fmt(selectedZone.historicos)} tone="slate" />
                </div>
                <div className="rounded-2xl border border-slate-200 p-4 text-sm leading-7 text-slate-600">
                  <div><b>Consumo demo:</b> {fmtM3(selectedZone.consumo_litros)}</div>
                  <div><b>Gateway base:</b> {selectedZone.gateway_id}</div>
                  {selectedZone.correccion_municipal && <div><b>Registro Excel:</b> D{selectedZone.raw_distrito_id}/Z{selectedZone.raw_zona_id}</div>}
                  <div><b>Infraestructuras base:</b> {fmt(selectedZone.infraestructuras_base)}</div>
                  <div><b>Centroide:</b> {Number(selectedZone.centro_lat).toFixed(5)}, {Number(selectedZone.centro_lon).toFixed(5)}</div>
                </div>
                <button onClick={() => setSelectedZone(null)} className="w-full rounded-2xl border px-3 py-2 text-sm font-black text-slate-600 hover:bg-slate-50">Limpiar selección</button>
              </div>
            ) : (
              <div className="rounded-2xl bg-slate-50 p-4 text-sm leading-6 text-slate-500">
                Haz clic en una zona o burbuja para ver consumo, medidores, estado, gateway e infraestructura base.
              </div>
            )}
          </div>

          <div className="rounded-[24px] border border-blue-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-slate-900"><BarChart3 className="text-blue-700" size={18} /><h2 className="font-black">Top zonas por {labelMetrica(metrica)}</h2></div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartZonas} layout="vertical" margin={{ left: 0, right: 10, top: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={116} tick={{ fontSize: 10 }} />
                <ChartTooltip />
                <Bar dataKey="valor" fill="#2563eb" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-[24px] border border-blue-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-slate-900"><Antenna className="text-blue-700" size={18} /><h2 className="font-black">Histograma por hora</h2></div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartHoras}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="hora" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <ChartTooltip />
                <Bar dataKey="consumo_m3" fill="#0891b2" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-2 text-xs leading-5 text-slate-500">Se alimenta desde lecturas cargadas en Cassandra. En demo rápida puede verse concentrado en una hora.</p>
          </div>

          <div className="rounded-[24px] border border-blue-100 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center gap-2 text-slate-900"><Filter className="text-blue-700" size={18} /><h2 className="font-black">Resumen filtrado</h2></div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-2xl bg-slate-50 p-3"><b>{fmt(zonasFiltradasGeojson.features.length)}</b><br/><span className="text-xs text-slate-500">zonas visibles</span></div>
              <div className="rounded-2xl bg-slate-50 p-3"><b>{fmt(medidoresFiltrados.length)}</b><br/><span className="text-xs text-slate-500">medidores muestra</span></div>
              <div className="rounded-2xl bg-slate-50 p-3"><b>{fmt((gateways.data ?? []).length || 14)}</b><br/><span className="text-xs text-slate-500">gateways</span></div>
              <div className="rounded-2xl bg-slate-50 p-3"><b>{fmt(estadoData.length)}</b><br/><span className="text-xs text-slate-500">estados</span></div>
            </div>
          </div>
        </aside>}
      </div>
    </div>
  );
}
