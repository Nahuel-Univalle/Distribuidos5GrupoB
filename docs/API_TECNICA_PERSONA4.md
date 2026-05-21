# SEMAPA API REST - Documentación Técnica Completa

**Proyecto**: Smart Water Cochabamba (SEMAPA)  
**Rol**: Persona 4 - Backend Engineer  
**Stack**: FastAPI + Cassandra + Redis  
**Versión API**: v1  

---

## 📋 Tabla de Contenidos

1. [Modelo de Datos](#modelo-de-datos)
2. [Estrategia de Particionamiento](#estrategia-de-particionamiento)
3. [Las 25 Consultas - Especificación Completa](#las-25-consultas)
4. [Endpoints REST](#endpoints-rest)
5. [Niveles de Consistencia](#niveles-de-consistencia)
6. [Estrategia de Caching](#estrategia-de-caching)
7. [Autenticación y Autorización](#autenticación-y-autorización)
8. [Ejemplos de Uso (cURL)](#ejemplos-de-uso)
9. [Consideraciones de Rendimiento](#consideraciones-de-rendimiento)
10. [Integración con Otros Servicios](#integración-con-otros-servicios)

---

## Modelo de Datos

### Tablas Principales

#### 1. `medidores` (Fact Table - Dimensión de Equipos)
```sql
CREATE TABLE medidores (
    medidor_id uuid PRIMARY KEY,
    mac text,
    numero_serie text,
    numero_contrato bigint,
    infraestructura_id uuid,
    modelo_id int,
    categoria_tarifa text,  -- R1..R4, C, CE, I, P, S
    gateway_id int,
    distrito_id int,
    zona_id int,
    latitud double,
    longitud double,
    fecha_instalacion date,
    estado text  -- ACTIVO | INACTIVO | FUERA_SERVICIO
);
```

**Índices secundarios**:
- `mac` → búsqueda rápida de medidores por MAC
- `numero_contrato` → búsqueda por contrato
- `numero_serie` → búsqueda por serie
- `categoria_tarifa` → filtrado por categoría
- `estado` → filtrado por estado

---

#### 2. `lecturas_por_medidor` (Time-Series - PRINCIPAL)
```sql
CREATE TABLE lecturas_por_medidor (
    medidor_id uuid,
    anio_mes int,  -- 202505
    fecha_hora timestamp,
    gateway_id int,
    lectura_litros bigint,
    consumo_litros int,  -- Diferencial
    status int,  -- 1=OK, 2=Manual, 3-9=errores
    
    PRIMARY KEY ((medidor_id, anio_mes), fecha_hora)
) WITH CLUSTERING ORDER BY (fecha_hora DESC)
  AND compression = {'sstable_compression': 'LZ4Compressor'}
  AND compaction = {'class': 'TimeWindowCompactionStrategy',
                    'compaction_window_unit': 'DAYS',
                    'compaction_window_size': 7};
```

**Estrategia de Partition Key**: `(medidor_id, anio_mes)`
- ✅ **Ventajas**:
  - Evita particiones gigantes (1 medidor × 1 mes = ~2880 lecturas máximo)
  - Locality: todas las lecturas de un medidor en un mes en el mismo nodo
  - Range queries eficientes por mes
  - Escalable horizontalmente (120k medidores × 12 meses = 1.44M particiones pequeñas)

- ❌ **Desventajas**:
  - No se puede consultar "todas las lecturas de hoy" sin ALLOW FILTERING
  - Requiere conocer el medidor_id para consultar

**Justificación**: Es la tabla más grande (~1M de registros/hora), por lo que el particionamiento debe ser fino. `medidor_id` solo generaría particiones de 43.2k registros/hora (demasiado grande); `anio_mes` solo, generaría 120k medidores × meses (ineficiente). **La combinación es óptima**.

---

#### 3. `lecturas_por_zona_dia` (Denormalización para Dashboard)
```sql
CREATE TABLE lecturas_por_zona_dia (
    distrito_id int,
    zona_id int,
    fecha date,
    hora int,  -- 0..23
    medidor_id uuid,
    consumo_litros int,
    categoria_tarifa text,
    
    PRIMARY KEY ((distrito_id, zona_id, fecha), hora, medidor_id)
);
```

**Partition Key**: `(distrito_id, zona_id, fecha)`
- ✅ Queries del dashboard agrupadas por zona/día
- ✅ Tamaño manejable (6 distritos × 50 zonas × 365 días = 109.5k particiones)
- ✅ Rango de horas optimizado para consultas horarias

**Alimentación**: ETL batch nocturno → Ingestor inserta en `lecturas_por_medidor`, luego Job nocturno agrega a esta tabla.

---

#### 4. `facturas`
```sql
CREATE TABLE facturas (
    numero_contrato bigint,
    periodo text,  -- '2025-05'
    factura_id uuid,
    medidor_id uuid,
    persona_id uuid,
    consumo_m3 decimal,
    monto_usd decimal,
    monto_bs decimal,
    tipo_cambio decimal,
    categoria_tarifa text,
    desglose text,  -- JSON con tramos aplicados
    fecha_emision timestamp,
    estado text,  -- PENDIENTE | PAGADA | ANULADA
    
    PRIMARY KEY ((numero_contrato), periodo)
) WITH CLUSTERING ORDER BY (periodo DESC);
```

**Partition Key**: `numero_contrato`
- Todas las facturas de un cliente agrupadas
- Rápida consulta "mis facturas" por contrato

---

#### 5. Catálogos (Pequeños, con Replicas Completas)
```
distritos: distrito_id → nombre, habitantes, sub_alcaldia_id
zonas: (distrito_id) → zona_id → nombre, gateway_id
gateways: gateway_id → nombre, latitud, longitud
modelos_medidor: modelo_id → marca, modelo, conectividad
tarifas: categoria → alias, precios por tramo
errores_iot: codigo → descripcion
personas: persona_id → CI/NIT, nombre, email, teléfono
```

---

## Estrategia de Particionamiento

| Tabla | Partition Key | Clustering | Razón |
|-------|---------------|-----------|-------|
| `medidores` | medidor_id | - | Lookup por equipo |
| `lecturas_por_medidor` | (medidor_id, anio_mes) | fecha_hora DESC | Time-series, evita particiones gigantes |
| `lecturas_por_zona_dia` | (distrito_id, zona_id, fecha) | hora, medidor_id | Dashboard queries |
| `facturas` | numero_contrato | periodo DESC | Historial del cliente |
| `usuarios_sistema` | username | - | Autenticación rápida |
| `lecturas_manuales` | medidor_id | fecha_hora DESC | Móvil, últimas lecturas primero |

---

## Las 25 Consultas - Especificación Completa

### CONSULTA 1: Consumo Promedio por Distrito en Rango Horario
**Endpoint**: `GET /api/v1/consultas/1?horas=8`

**Lógica**:
- Agrupa consumo por distrito en bloques de N horas (default 8)
- Retorna rangos 0-8h, 8-16h, 16-24h

**Query Cassandra**:
```sql
SELECT distrito_id, hora, consumo_litros FROM lecturas_por_zona_dia
  -- Procesamiento en aplicación: agrupar por hora / horas
```

**Respuesta (200 OK)**:
```json
[
  {
    "distrito": "TUNARI",
    "rango": "00:00-08:00",
    "consumo_m3": 1254.004,
    "consumo_promedio_litros": 156750,
    "muestras": 8,
    "unidad": "m³"
  },
  ...
]
```

**Caché**: TTL 600s | Key: `q:1:cpd:8`  
**Consistency**: ONE (analítica)

---

### CONSULTA 2: Comparativa Consumo Últimas 4 Semanas
**Endpoint**: `GET /api/v1/consultas/2?distritos=1,2,3`

**Lógica**:
- Compara consumo entre distritos para cada semana ISO
- Útil para detectar anomalías semanales

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "semana": "S1",
    "consumo_m3": 125000.0,
    "consumo_litros": 125000000000
  },
  {
    "distrito": "TUNARI",
    "semana": "S2",
    "consumo_m3": 127500.0,
    "consumo_litros": 127500000000
  },
  ...
]
```

**Caché**: TTL 600s | Key: `q:2:comp:{distritos}`

---

### CONSULTA 3: Identificación de Consumos Excesivos
**Endpoint**: `GET /api/v1/consultas/3?umbral_m3=45.0`

**Lógica**:
- Identifica contratos residenciales con consumo > 45 m³/mes
- Estándar ONU: 300 L/persona/día × 5 personas × 30 días = 45 m³

**Respuesta**:
```json
[
  {
    "numero_contrato": 65412354,
    "tarifa": "R2",
    "consumo_m3": 110.0,
    "exceso_m3": 65.0,
    "exceso_porcentaje": 144.44
  },
  ...
]
```

**Caché**: TTL 600s | Key: `q:3:excesivos:{umbral_m3}`

---

### CONSULTA 4: Medidores Activos por Distrito y Zona
**Endpoint**: `GET /api/v1/consultas/4`

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "zona": "SARCOBAMBA",
    "medidores_activos": 2651
  },
  ...
]
```

**Caché**: TTL 600s | Key: `q:4:medidores_activos`

---

### CONSULTA 5: Medidores Fuera de Servicio
**Endpoint**: `GET /api/v1/consultas/5`

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "zona": "SARCOBAMBA",
    "medidores_fuera_servicio": 651
  },
  ...
]
```

---

### CONSULTA 6: Modelos con Mayor Tasa de Fallos
**Endpoint**: `GET /api/v1/consultas/6`

**Respuesta**:
```json
[
  {
    "modelo_id": 2,
    "modelo_nombre": "Siconia WATER WM-NB",
    "total_medidores": 3500,
    "fallos_reportados": 2622,
    "tasa_fallo": 0.7491,
    "tasa_fallo_pct": 74.91
  },
  ...
]
```

---

### CONSULTA 7: Consumo Promedio Mensual por Tarifa y Distrito
**Endpoint**: `GET /api/v1/consultas/7`

**Respuesta (matriz)**:
```json
[
  {
    "distrito": "TUNARI",
    "categoria_tarifa": "R1",
    "consumo_m3_total": 6818.0,
    "consumo_m3_promedio_diario": 227.27,
    "muestras": 30
  },
  ...
]
```

---

### CONSULTA 8: Zonas con Más Medidores Anómalos
**Endpoint**: `GET /api/v1/consultas/8`

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "zona": "CONDEBAMBA",
    "latitud": -17.385,
    "longitud": -66.258,
    "medidores_totales": 5000,
    "consumo_cero": 120,
    "consumo_excesivo": 80,
    "total_anomalias": 200,
    "tasa_anomalia": 0.04
  },
  ...
]
```

---

### CONSULTA 9: Lecturas Fallidas Último Mes
**Endpoint**: `GET /api/v1/consultas/9`

**Respuesta**:
```json
[
  {
    "modelo_id": 1,
    "modelo_nombre": "ITC 100",
    "status_1_ok": 1000,
    "status_2_manual": 50,
    "status_3_plus_errores": 92,
    "total_fallidas": 92,
    "tasa_falla": 0.0806
  },
  ...
]
```

---

### CONSULTA 10: Porcentaje Medidores >4 Años
**Endpoint**: `GET /api/v1/consultas/10?anios=4`

**Respuesta**:
```json
{
  "total_medidores": 120000,
  "medidores_antiguos": 6256,
  "años_minimo": 4,
  "fecha_cutoff": "2021-05-19",
  "porcentaje": 5.21
}
```

---

### CONSULTA 11: Consumo Per Cápita Residencial
**Endpoint**: `GET /api/v1/consultas/11`

**Respuesta**:
```json
[
  {
    "zona": "SARCOBAMBA",
    "categoria_residencial": "R1",
    "consumo_total_m3": 2772.0,
    "medidores": 150,
    "poblacion_zona": 750,
    "per_capita_litros_dia": 123.2,
    "per_capita_m3_mes": 3.7
  },
  ...
]
```

---

### CONSULTA 12: Top 3 Consumidores por Distrito
**Endpoint**: `GET /api/v1/consultas/12`

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "rank": 1,
    "numero_contrato": 123545,
    "numero_serie": "SN=254-41269-1411",
    "consumo_m3": 77.0
  },
  ...
]
```

---

### CONSULTA 13: Zonas que Requieren Renovación
**Endpoint**: `GET /api/v1/consultas/13`

**Respuesta**:
```json
[
  {
    "distrito": "MOLLE",
    "zona": "VILLA BUSCH",
    "total_medidores": 1235,
    "activos": 1100,
    "inactivos": 95,
    "fuera_servicio": 40,
    "total_errores": 135,
    "tasa_error": 0.1094,
    "tasa_error_pct": 10.94,
    "prioridad": "ALTA"
  },
  ...
]
```

---

### CONSULTA 14: Zonas con Errores por Distrito (SORPRESA 1)
**Endpoint**: `GET /api/v1/consultas/14?distrito=1`

**Respuesta**:
```json
[
  {
    "zona": "SARCOBAMBA",
    "medidores_totales": 2651,
    "medidores_con_falla": 400,
    "tasa_falla": 0.1509,
    "tasa_falla_pct": 15.09
  },
  ...
]
```

---

### CONSULTA 15: Cobertura de Antenas
**Endpoint**: `GET /api/v1/consultas/15`

**Respuesta**:
```json
[
  {
    "antena_gateway": "LoRaWan-Teleferico",
    "zona": "SARCOBAMBA",
    "medidores_conectados": 16446
  },
  {
    "antena_gateway": "LoRaWan-Teleferico",
    "zona": "VILLA BUSCH",
    "medidores_conectados": 18762
  },
  ...
]
```

---

### CONSULTA 16: Proyección Demanda 5 Años (2.6% anual)
**Endpoint**: `GET /api/v1/consultas/16?crecimiento_anual_pct=2.6`

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "consumo_2025_m3": 42983.0,
    "consumo_2026_m3": 44101.0,
    "consumo_2027_m3": 45247.0,
    "consumo_2028_m3": 46424.0,
    "consumo_2029_m3": 47631.0
  },
  ...
]
```

---

### CONSULTA 17: Impacto Cambio Tarifa (SORPRESA 2)
**Endpoint**: `GET /api/v1/consultas/17?desde_tarifa=P&hacia_tarifa=R4`

**Respuesta**:
```json
{
  "numero_contratos_afectados": 11218,
  "tarifa_origen": "P",
  "tarifa_destino": "R4",
  "tarifa_origen_nombre": "Preferencial",
  "tarifa_destino_nombre": "Residencial R4",
  "ingreso_actual_mes_usd": 5701161.1,
  "ingreso_nuevo_mes_usd": 10817268.55,
  "incremento_usd": 5116107.45,
  "incremento_porcentaje": 89.79
}
```

---

### CONSULTA 18: Medidores Sin Reporte
**Endpoint**: `GET /api/v1/consultas/18?dias=7`

**Respuesta**:
```json
[
  {
    "numero_serie": "SN=254-41269-1411",
    "distrito": "MOLLE",
    "zona": "SARCOBAMBA",
    "direccion": "Av. Juan Capriles y Anaya Nro 125",
    "dias_sin_reporte": 7
  },
  ...
]
```

---

### CONSULTA 19: Proyección Ingresos Mes
**Endpoint**: `GET /api/v1/consultas/19`

**Respuesta**:
```json
[
  {
    "categoria": "R1",
    "alias": "Residencial R1",
    "medidores_activos": 30000,
    "tarifa_usd_mes": 1.4,
    "ingreso_mes_usd": 42000.0
  },
  {
    "categoria": "R2",
    "alias": "Residencial R2",
    "medidores_activos": 25000,
    "tarifa_usd_mes": 2.8,
    "ingreso_mes_usd": 70000.0
  },
  ...
  {
    "categoria": "TOTAL",
    "alias": "Total de Ingresos",
    "medidores_activos": 120000,
    "ingreso_mes_usd": 567823.45
  }
]
```

---

### CONSULTA 20: Consumo Mínimo Residencial
**Endpoint**: `GET /api/v1/consultas/20?consumo_minimo_m3=12.0`

**Respuesta**:
```json
{
  "consumo_minimo_m3": 12.0,
  "precio_por_m3_usd": 1.4,
  "medidores_bajo_minimo": 5000,
  "monto_total_cobrar_usd": 84000.0,
  "monto_por_medidor_usd": 16.8
}
```

---

### CONSULTA 21: Ingresos en Pies Cúbicos
**Endpoint**: `GET /api/v1/consultas/21`

**Respuesta**:
```json
{
  "consumo_total_m3": 500000.0,
  "consumo_total_pies3": 17657350.0,
  "litros_totales": 500000000000,
  "precio_promedio_usd_m3": 5.0,
  "ingreso_total_usd": 2500000.0,
  "ingreso_por_pies3_usd": 0.1415
}
```

---

### CONSULTA 22: Detección de Anomalías (SORPRESA 3)
**Endpoint**: `GET /api/v1/consultas/22`

**Respuesta**:
```json
{
  "fecha_analisis": "2025-05-19",
  "anomalias_detectadas": {
    "consumo_cero_prolongado": 0,
    "incrementos_repentinos": 0,
    "patrones_nocturnos_anomalos": 1,
    "total_medidores_anomalos": 1
  },
  "recomendacion": "Revisar zonas con patrones nocturnos elevados - posibles fugas"
}
```

---

### CONSULTA 23: Análisis Cobertura Gateways (SORPRESA 4)
**Endpoint**: `GET /api/v1/consultas/23`

**Respuesta**:
```json
[
  {
    "gateway_id": 1,
    "nombre": "LoRaWan-Teleferico",
    "latitud": -17.385,
    "longitud": -66.258,
    "medidores_totales": 35000,
    "medidores_activos": 33000,
    "medidores_inactivos": 2000,
    "tasa_actividad_pct": 94.29,
    "zonas_cobertura": 12
  },
  ...
]
```

---

### CONSULTA 25: Análisis Predictivo Estratégico (SORPRESA 5)
**Endpoint**: `GET /api/v1/consultas/25`

**Respuesta**:
```json
{
  "fecha_analisis": "2025-05-19",
  "distritos_analizados": 6,
  "resultados": [
    {
      "distrito_id": 1,
      "medidores_totales": 30000,
      "medidores_activos": 28500,
      "tasa_cobertura_pct": 95.0,
      "nivel_salud": "ÓPTIMO",
      "prioridad_accion": "MANTENIMIENTO"
    },
    ...
  ],
  "recomendaciones_estrategicas": [
    "Invertir en zonas con cobertura <75%",
    "Implementar mantenimiento preventivo en zonas ÓPTIMAS",
    ...
  ]
}
```

---

## Endpoints REST

### Base URL
```
http://localhost:8000/api/v1
```

### Autenticación
Todos los endpoints requieren **JWT Bearer token**:
```bash
Authorization: Bearer eyJhbGc...
```

### Categorías de Endpoints

#### 1. Autenticación
```
POST   /auth/login          # Login usuario
GET    /auth/me             # Obtener datos usuario actual
POST   /auth/logout         # Logout (stateless)
```

#### 2. Consultas (Las 25)
```
GET    /consultas/1         # Consumo promedio distrito (8h)
GET    /consultas/2         # Comparativa 4 semanas
GET    /consultas/3         # Consumos excesivos
GET    /consultas/4         # Medidores activos
GET    /consultas/5         # Medidores fuera servicio
GET    /consultas/6         # Modelos con fallos
GET    /consultas/7         # Consumo por tarifa/distrito
GET    /consultas/8         # Zonas anómalas
GET    /consultas/9         # Lecturas fallidas mes
GET    /consultas/10        # Medidores >4 años
GET    /consultas/11        # Per cápita residencial
GET    /consultas/12        # Top 3 consumidores/distrito
GET    /consultas/13        # Zonas renovación
GET    /consultas/14        # Errores por distrito
GET    /consultas/15        # Cobertura antenas
GET    /consultas/16        # Proyección 5 años
GET    /consultas/17        # Impacto cambio tarifa
GET    /consultas/18        # Medidores sin reporte
GET    /consultas/19        # Proyección ingresos mes
GET    /consultas/20        # Consumo mínimo residencial
GET    /consultas/21        # Ingresos pies3
GET    /consultas/22        # Detección anomalías
GET    /consultas/23        # Cobertura gateways
GET    /consultas/25        # Análisis predictivo
```

#### 3. Dashboard
```
GET    /dashboard/kpis      # KPIs personalizados por rol
```

#### 4. Búsqueda
```
GET    /buscar?q=...        # Busca por contrato/MAC/serie/documento
```

#### 5. Lecturas (Móvil)
```
POST   /lecturas/manual     # Registrar lectura manual + foto + geoloc
```

#### 6. Facturación
```
GET    /facturas/{contrato}/{periodo}  # Obtener factura PDF
```

---

## Niveles de Consistencia

| Operación | CL | Justificación |
|-----------|----|----|
| `POST /login` | LOCAL_QUORUM | Crítico: evitar auth inconsistente |
| `GET /consultas/*` | ONE | Analítica: lecturas débiles aceptables |
| `GET /dashboard/kpis` | ONE | KPIs pueden ser ligeramente stale |
| `POST /lecturas/manual` | LOCAL_QUORUM | Importante: no perder lecturas |
| `GET /facturas/*` | LOCAL_QUORUM | Crítico: datos monetarios |
| `GET /buscar` | ONE | Búsquedas: eventual consistency OK |

**Notas**:
- LOCAL_QUORUM requiere 2 nodos en cluster de 2 (tanto sea disponible)
- ONE es más rápido pero eventual consistency
- Por defecto se usa LOCAL_QUORUM; queries analíticas se especifican con `profile="analytics"` → ONE

---

## Estrategia de Caching

### Capas de Caché

1. **Redis (TTL variable)** - Por query
   - `q:1:cpd:8` → 600s → Consulta 1 con rango 8h
   - `q:19:proyeccion_ingresos` → 600s → Proyección ingresos
   - `dash:base` → 60s → KPIs base rápidos

2. **HTTP Client-side** (Swagger UI / Browser)
   - Cache-Control: max-age=60 (en headers opcionales)

3. **Session en Memoria** (FastAPI)
   - Replicación de datos de catálogos (distritos, gateways, etc.)

### TTL por Tipo

| Tipo | TTL | Razón |
|------|-----|-------|
| KPI real-time | 60s | Frecuente actualización |
| Consulta pesada | 600s | 10 min, menos crítica |
| Catálogos | 3600s | 1 hora, cambios raros |
| Ingresos/Proyecciones | 600s | 10 min, importante |

### Invalidación

- **Manual**: Cuando se inserta factura: `await redis.delete("q:19:*")`
- **TTL**: Automática por Redis
- **Fallo**: Si Redis no disponible, query se ejecuta sin cache

---

## Autenticación y Autorización

### Flujo JWT

```
1. POST /auth/login
   Request: {"username": "admin", "password": "xxxx"}
   Response: {"access_token": "eyJ0...", "rol": "ALCALDIA", ...}

2. Cliente almacena token en localStorage

3. Request posterior
   Header: "Authorization: Bearer eyJ0..."
   
4. FastAPI valida token
   - Decodifica con JWT_SECRET
   - Verifica exp
   - Extrae user["sub"] y user["rol"]
```

### Roles

| Rol | Permisos | KPIs Adicionales |
|-----|----------|------------------|
| ALCALDIA | Leer reportes, proyecciones | población_beneficiaria, cobertura |
| GERENCIA | Leer KPIs técnicos | medidores_por_modelo, tasas de falla |
| CONTABILIDAD | Leer facturas, ingresos | ingresos por categoría, proyecciones |

### Implementación

```python
@router.get("/consultas/19")
async def query_19(user: dict = Depends(current_user)):
    # user = {"sub": "admin", "rol": "CONTABILIDAD", "exp": ...}
    return {...}

# Si se requiere rol específico:
def require_roles(roles):
    def _guard(user: dict = Depends(current_user)) -> dict:
        if user.get("rol") not in roles:
            raise HTTPException(403, "Unauthorized")
        return user
    return _guard

@router.get("/consultas/sensitive")
async def sensitive_query(user: dict = Depends(require_roles(["ALCALDIA"]))):
    return {...}
```

---

## Ejemplos de Uso

### 1. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"12345"}'
```

**Respuesta**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "rol": "ALCALDIA",
  "nombre": "Administrador",
  "email": "admin@semapa.bo"
}
```

---

### 2. Consulta 1 (Consumo Promedio Distrito)

```bash
TOKEN="eyJhbGciOi..."

curl -X GET "http://localhost:8000/api/v1/consultas/1?horas=8" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta**:
```json
[
  {
    "distrito": "TUNARI",
    "rango": "00:00-08:00",
    "consumo_m3": 1254.004,
    "consumo_promedio_litros": 156750.5,
    "muestras": 8,
    "unidad": "m³"
  },
  {
    "distrito": "TUNARI",
    "rango": "08:00-16:00",
    "consumo_m3": 6854.221,
    "consumo_promedio_litros": 856777.625,
    "muestras": 8,
    "unidad": "m³"
  },
  ...
]
```

---

### 3. Consulta 19 (Proyección Ingresos)

```bash
curl -X GET "http://localhost:8000/api/v1/consultas/19" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta**:
```json
[
  {
    "categoria": "R1",
    "alias": "Residencial R1",
    "medidores_activos": 30000,
    "tarifa_usd_mes": 1.4,
    "ingreso_mes_usd": 42000.0
  },
  {
    "categoria": "TOTAL",
    "alias": "Total de Ingresos",
    "medidores_activos": 120000,
    "ingreso_mes_usd": 567823.45
  }
]
```

---

### 4. Lectura Manual (Móvil)

```bash
curl -X POST http://localhost:8000/api/v1/lecturas/manual \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "numero_contrato": 123456,
    "lectura_litros": 456789,
    "lat": -17.394,
    "lon": -66.157,
    "foto_url": "s3://bucket/foto_2025_05_19_145523.jpg"
  }'
```

**Respuesta**:
```json
{
  "ok": true,
  "medidor_id": "e7c1a2b3-4d5e-6f7g-8h9i-0j1k2l3m4n5o",
  "timestamp": "2025-05-19T14:55:23.123456Z"
}
```

---

### 5. KPIs por Rol

```bash
curl -X GET http://localhost:8000/api/v1/dashboard/kpis \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta (ALCALDIA)**:
```json
{
  "medidores_total": 120000,
  "medidores_activos": 115000,
  "medidores_inactivos": 4000,
  "medidores_fuera_servicio": 1000,
  "poblacion_beneficiaria": 900000,
  "cobertura": "100% urbano (proxy)"
}
```

---

### 6. Búsqueda Unificada

```bash
# Por contrato
curl -X GET "http://localhost:8000/api/v1/buscar?q=123456" \
  -H "Authorization: Bearer $TOKEN"

# Por MAC
curl -X GET "http://localhost:8000/api/v1/buscar?q=AB:CD:12:34:56:78" \
  -H "Authorization: Bearer $TOKEN"

# Por serie
curl -X GET "http://localhost:8000/api/v1/buscar?q=SN=254-41269-1411" \
  -H "Authorization: Bearer $TOKEN"

# Por documento
curl -X GET "http://localhost:8000/api/v1/buscar?q=12345678" \
  -H "Authorization: Bearer $TOKEN"
```

**Respuesta**:
```json
{
  "q": "123456",
  "count": 2,
  "results": [
    {
      "tipo": "medidor",
      "payload": {
        "medidor_id": "e7c1a2b3-4d5e-6f7g-8h9i-0j1k2l3m4n5o",
        "mac": "AB:CD:12:34:56:78",
        "numero_contrato": 123456,
        "categoria_tarifa": "R2"
      }
    },
    {
      "tipo": "persona",
      "payload": {
        "persona_id": "f8d2b3c4-5e6f-7g8h-9i0j-1k2l3m4n5o6p",
        "documento": "123456",
        "nombre": "Juan Pérez"
      }
    }
  ]
}
```

---

## Consideraciones de Rendimiento

### Tiempos de Respuesta Objetivo

| Consulta | Timeout | Caché | CL | Notas |
|----------|---------|-------|----|----|
| Lectura simple (contrato) | <100ms | NO | QUORUM | Lookup + Cassandra fast path |
| KPI base | <200ms | YES | ONE | Agregado, pero small data |
| Consulta analítica (sin caché) | 1-2s | YES | ONE | Scans + agregación |
| Facturación | <500ms | NO | QUORUM | Crítico |
| Búsqueda | <300ms | NO | ONE | Index + lookup |

### Estrategias de Optimización

#### 1. **ALLOW FILTERING - Cuándo Usar**
```python
# ✅ BUENO: Usa índice primario
SELECT * FROM medidores WHERE medidor_id = ?

# ⚠️ ACEPTABLE: índice secundario
SELECT * FROM medidores WHERE estado = 'ACTIVO' ALLOW FILTERING

# ❌ EVITAR: escanea particiones completas
SELECT * FROM medidores WHERE nombre LIKE '%Juan%' ALLOW FILTERING
```

#### 2. **Prepared Statements**
```python
# ✅ SIEMPRE usar prepared statements para repetidas
stmt = session.prepare("SELECT * FROM medidores WHERE medidor_id = ?")
session.execute(stmt, (medidor_id,))

# ❌ EVITAR: string interpolation
query = f"SELECT * FROM medidores WHERE medidor_id = '{medidor_id}'"
```

#### 3. **Pool de Conexiones**
```python
# Cassandra driver auto-gestiona pool
# Default: 25 connections por nodo
# Ajustar si CQL timeouts persisten
settings.CASSANDRA_POOL_SIZE = 50
```

#### 4. **Batch Inserts**
```python
# Para Ingestor: usar BATCH para múltiples lecturas
BEGIN BATCH
  INSERT INTO lecturas_por_medidor (...) VALUES (...)
  INSERT INTO lecturas_por_medidor (...) VALUES (...)
  INSERT INTO lecturas_por_zona_dia (...) VALUES (...)
APPLY BATCH;
```

#### 5. **Pagination**
Cuando una consulta retorna >10k registros:
```python
@router.get("/medidores")
async def list_medidores(skip: int = 0, limit: int = 100):
    # Implementar cursor pagination en aplicación
    offset = skip
    rows = cassandra_client.execute_raw(
        "SELECT * FROM medidores LIMIT ?",
        (limit + 1,),
        profile="analytics"
    )
    return {"data": rows[:limit], "has_more": len(rows) > limit}
```

#### 6. **Denormalización Estratégica**
```python
# En lugar de JOIN:
SELECT m.modelo_id, m.modelo
  FROM medidores JOIN modelos_medidor USING (modelo_id)  # ❌ NO FUNCIONA

# Usar denormalización: modelo_nombre en medidores
SELECT medidor_id, modelo_nombre FROM medidores
```

---

## Integración con Otros Servicios

### Con Persona 2 (Seeder)

**Datos que el Seeder debe insertar**:
```
distritos(distrito_id, nombre, habitantes)
zonas(distrito_id, zona_id, nombre, gateway_id)
gateways(gateway_id, nombre, latitud, longitud)
modelos_medidor(modelo_id, marca, modelo, conectividad)
tarifas(categoria, alias, fijo_m3, usd_mes, r_13_25, ...)
medidores(medidor_id, mac, numero_serie, numero_contrato, ..., estado='ACTIVO')
personas(persona_id, tipo, documento, nombre, ...)
infraestructuras(infraestructura_id, persona_id, distrito_id, zona_id, ...)
```

**Format CSV esperado**: Ver `data/seeds/*.csv`

---

### Con Persona 3 (IoT Ingestor)

**Flujo de datos**:
```
Simulador (lora-data/*.txt)
    ↓
Ingestor (watchdog) → Redis dedup → Cassandra
    ├→ INSERT lecturas_raw (auditoría)
    └→ INSERT lecturas_por_medidor (analítica)
        └→ ETL nocturno → INSERT lecturas_por_zona_dia
```

**Shared Tables**:
- `lecturas_raw` - Raw desde IoT
- `lecturas_por_medidor` - Procesada, particionada
- `lecturas_por_zona_dia` - Denormalizada para dashboard

**Coordinación**:
- Ingestor inserta con status=1 (OK)
- API puede insertar status=2 (Manual, móvil)
- Reportes usan status para filtrar anomalías

---

### Con Persona 5 (Frontend)

**Endpoints críticos para Web/Mobile**:

1. **Autenticación**:
   - POST `/auth/login`
   - GET `/auth/me`
   - POST `/auth/logout`

2. **Dashboard (KPIs)**:
   - GET `/dashboard/kpis`

3. **Consultas (Reportes)**:
   - GET `/consultas/{1..25}`

4. **Búsqueda**:
   - GET `/buscar?q=...`

5. **Facturación**:
   - GET `/facturas/{contrato}/{periodo}` → PDF

6. **Móvil (App)**:
   - POST `/lecturas/manual`
   - GET `/consultas/18` (medidores sin reporte)

---

## Monitoreo y Debugging

### Logs

```python
# Habilitar logs detallados
settings.LOG_LEVEL = "DEBUG"  # En .env

# Ver timeouts de Cassandra
loguru logger.enable("cassandra")
```

### Health Check

```bash
curl http://localhost:8000/health
```

**Respuesta**:
```json
{"status": "ok", "service": "semapa-api"}
```

### Swagger/OpenAPI

```bash
curl http://localhost:8000/api/v1/docs  # Swagger UI
curl http://localhost:8000/api/v1/openapi.json  # OpenAPI JSON
```

---

## Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2025-05-19 | Implementación inicial: 25 consultas, 6 endpoints críticos |

---

## Contacto y Soporte

- **Autor**: Persona 4 - Backend Engineer
- **Proyecto**: SEMAPA (Smart Water Cochabamba)
- **Equipo**: 5 desarrolladores
- **PM**: Persona 1 (Tech Lead)

---

**Fin de Documentación Técnica**
