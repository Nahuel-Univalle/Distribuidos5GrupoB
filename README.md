<div align="center">

# 💧 SEMAPA — Gestión Inteligente de Agua Potable

**Sistema distribuido para la gestión inteligente de agua potable de SEMAPA — Práctica 5 Cassandra**

[![Cassandra](https://img.shields.io/badge/Cassandra-4.1-1287B1?logo=apachecassandra)](https://cassandra.apache.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev/)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker)](https://www.docker.com/)

**Módulo Denis:** poblamiento masivo, georreferenciación, mapa territorial, filtros y reparación geográfica para Cercado.

</div>

---

## 📌 Resumen del proyecto

Este proyecto implementa una arquitectura distribuida para SEMAPA usando **Apache Cassandra** como base de datos NoSQL distribuida. El sistema simula la operación de una red de medidores IoT de agua potable conectados a radiobases LoRaWAN, permitiendo almacenar lecturas, visualizar consumo geográficamente, consultar indicadores estratégicos y generar recibos.

La práctica pide trabajar con:

- **80.000 personas naturales**.
- **5.000 personas jurídicas**.
- **100.000 infraestructuras**.
- **120.000 medidores IoT**.
- **32 radiobases/gateways LoRaWAN**.
- **9 categorías tarifarias**.
- Lecturas históricas desde **2025-04-01**.
- Dashboard con **totalizador, medidores, población beneficiaria, mapa de calor o burbujas, histograma por hora y filtros**.

La versión actual está ajustada para demostrar la parte territorial sobre el **municipio Cercado de Cochabamba**, usando **15 distritos** y zonas/subdistritos de la tabla de la Práctica 5. Los datos fuera de Cercado no se muestran y el exterior del municipio se representa en gris.

---

## 🧭 Rama recomendada para trabajar

Crear la rama desde `Grupo2Main` con este nombre:

```bash
feature/denis-geodatos-cercado
```

Nombre alternativo si quieren algo más corto:

```bash
denis/geodatos-cercado
```

---

## 🏗️ Arquitectura general

```text
Medidores IoT / LoRaWAN
        │
        ▼
Simulator  ── genera archivos/eventos de lectura
        │
        ▼
Ingestor  ── lee lecturas y las inserta
        │
        ▼
Cassandra Cluster 2 nodos
        │
        ├── FastAPI x2 detrás de Nginx
        │       ├── Dashboard / mapa
        │       ├── Consultas estratégicas
        │       ├── Facturación
        │       └── Búsqueda
        │
        ├── Redis cache
        ├── RabbitMQ mensajería
        ├── PDF Service
        ├── Workers email / SMS / WhatsApp
        └── React Web
```

Documentación relacionada:

```text
docs/arquitectura.md
docs/conceptos-cassandra.md
docs/informe-tecnico.md
docs/denis-seeder-mapa.md
docs/denis-frontend-geodatos.md
docs/denis-mapa-v14-practica5-cercado.md
```

---

## 🛠️ Stack tecnológico

| Capa | Tecnología |
|---|---|
| Base de datos | Apache Cassandra 4.1, 2 nodos |
| Backend | Python 3.11 + FastAPI |
| Cache | Redis |
| Mensajería | RabbitMQ |
| Frontend | React 18 + Vite + TypeScript |
| Mapa | Leaflet, OpenStreetMap, capas WMS/GeoJSON |
| PDF | ReportLab |
| SMTP demo | Mailhog |
| Orquestación | Docker Compose |

---

## 📁 Estructura importante del proyecto

```text
SEMAPA-Denis-patch/
├── docker-compose.yml
├── README.md
├── docs/
│   ├── arquitectura.md
│   ├── conceptos-cassandra.md
│   ├── informe-tecnico.md
│   ├── denis-seeder-mapa.md
│   ├── denis-frontend-geodatos.md
│   └── denis-mapa-v14-practica5-cercado.md
├── infra/
│   ├── cassandra/init/02_tables.cql
│   ├── cassandra/init/03_indexes.cql
│   └── nginx/
├── services/
│   ├── api/app/routers/mapa.py
│   ├── seeder/seed.py
│   ├── seeder/geo_reference.py
│   ├── seeder/repair_geo.py
│   ├── seeder/seed_lecturas.py
│   ├── seeder/excel_loader.py
│   ├── ingestor/
│   ├── simulator/
│   ├── pdf-service/
│   ├── worker-email/
│   ├── worker-sms/
│   └── worker-whatsapp/
├── web/src/pages/Mapa.tsx
├── web/src/
└── data/seeds/
```

### Archivos principales de la parte Denis

| Archivo | Función |
|---|---|
| `services/seeder/seed.py` | Genera personas, infraestructuras, medidores, tarifas, gateways y catálogos. |
| `services/seeder/geo_reference.py` | Contiene la referencia geográfica por `distrito_id + zona_id`, limitada a Cercado. |
| `services/seeder/repair_geo.py` | Repara coordenadas ya cargadas en Cassandra sin borrar datos. |
| `services/seeder/seed_lecturas.py` | Genera lecturas históricas o demo. |
| `services/api/app/routers/mapa.py` | Endpoints del mapa, filtros y datos geográficos. |
| `web/src/pages/Mapa.tsx` | Vista del mapa, burbujas, calor, puntos, filtros y capas. |

---

## ⚙️ Requisitos

- Docker Desktop.
- Docker Compose v2.
- 8 GB RAM mínimo; recomendado 16 GB.
- Windows PowerShell, CMD, Git Bash o terminal Linux.
- Espacio libre recomendado: 20 GB.

---

## 🚀 Ejecución rápida en Windows PowerShell

Desde la carpeta del proyecto:

```powershell
cd C:\Users\denis\Downloads\SEMAPA-Denis-patch
```

Construir servicios principales:

```powershell
docker compose build web api-1 api-2 seeder
```

Levantar el sistema:

```powershell
docker compose up -d
```

Reparar coordenadas para que todo quede dentro de Cercado:

```powershell
docker compose run --rm seeder python repair_geo.py
```

Limpiar cache:

```powershell
docker exec semapa-redis redis-cli FLUSHALL
```

Reiniciar servicios web/API:

```powershell
docker compose restart api-1 api-2 web nginx
```

Abrir en navegador:

```text
http://localhost
http://localhost/mapa
```

Después de actualizar frontend, presionar:

```text
Ctrl + F5
```

---

## 🌱 Cargar datos desde cero

Usar esto solo si se quiere regenerar toda la base. Si la base ya está cargada, primero probar con `repair_geo.py`.

### 1. Poblar catálogos, personas, infraestructuras y medidores

```powershell
docker compose run --rm seeder python seed.py
```

Debe dejar aproximadamente:

```text
85.000 personas
100.000 infraestructuras
120.000 medidores
32 gateways
9 tarifas
```

### 2. Cargar lecturas demo rápida

No ejecutar `seed_lecturas.py` sin variables si no quieres esperar horas. La carga completa puede superar 100 millones de lecturas.

Comando recomendado para defensa:

```powershell
docker compose run --rm -e LECTURAS_LIMITE_MEDIDORES=5000 -e LECTURAS_STEP_DIAS=7 -e LECTURAS_POR_DIA=1 seeder python seed_lecturas.py
```

Resultado esperado aproximado:

```text
295.000 lecturas en 1 a 2 minutos
```

Carga completa real, solo si se desea dejar corriendo mucho tiempo:

```powershell
docker compose run --rm -e LECTURAS_PRESET=full -e LECTURAS_CONFIRMAR_FULL=SI seeder python seed_lecturas.py
```

---

## 🔧 Reparar solo coordenadas sin borrar datos

Este es el comando más importante para la parte geográfica:

```powershell
docker compose run --rm seeder python repair_geo.py
```

Repara:

```text
infraestructuras
medidores
gateways
```

No cambia:

```text
personas
contratos
tarifas
cantidades
lecturas
```

Al finalizar debe mostrar una validación parecida a:

```text
Coordenadas reparadas: 100000 infraestructuras, 120000 medidores y 32 gateways
Validación interna: fuera_de_cercado infra=0 medidores=0 gateways=0
```

Luego ejecutar:

```powershell
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

---

## 🗺️ Mapa y dashboard geográfico

La pantalla principal para defender la parte de Denis es:

```text
http://localhost/mapa
```

El mapa permite demostrar:

- Poblamiento de **120.000 medidores**.
- Distribución en **100.000 infraestructuras**.
- Ubicación solo dentro del **municipio Cercado**.
- 15 distritos y zonas/subdistritos de la práctica.
- 32 gateways/radiobases.
- Estados de medidores: activos, fuera de servicio, históricos, dañados, reemplazados.
- Mapa con **burbujas**.
- Mapa de **calor**.
- Vista de **puntos** individuales.
- Vista **mixta**.
- Capas municipales ocultables.
- Exterior de Cercado en gris.

### Filtros disponibles

```text
Estado
Tarifa / categoría
Distrito
Zona
Gateway
Tipo de visualización: Burbujas, Calor, Puntos, Mixto
Métrica: consumo, medidores, activos, fallas
Tamaño de muestra
Buscador por contrato, MAC, serie o UUID
```

### Capas del mapa

El botón **Capas** permite ocultar/mostrar:

```text
Fuera de Cercado en gris
Zonas SEMAPA
Gateways / radiobases
Distritos municipales
Comunas
Subdistritos
Límite Cercado
Área urbana
Manzanas
```

---

## ✅ Requisitos del Word cubiertos por el mapa

El Word pide que el dashboard tenga:

| Requisito | Estado en el proyecto |
|---|---|
| Totalizador de consumo | Incluido en dashboard/mapa. |
| Cantidad de medidores | Incluido: 120.000 medidores. |
| Población beneficiaria | Incluido: 85.000 registros base/personas. |
| Mapa de calor o burbujas por distrito | Incluido: visualización Calor y Burbujas. |
| Histograma por hora del consumo promedio | Incluido en panel inferior/lateral del mapa. |
| Filtros por zona | Incluido. |
| Filtro/búsqueda por medidor | Incluido por contrato, MAC, serie o UUID. |
| Filtro por categoría de usuario | Incluido como tarifa/categoría. |
| Filtro por fecha | Pendiente de confirmar visualmente o extender si el equipo lo requiere. |

---

## 🔍 Verificación rápida de datos en Cassandra

### Personas

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM personas;"
```

Esperado:

```text
85000
```

### Infraestructuras

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM infraestructuras;"
```

Esperado:

```text
100000
```

### Medidores

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM medidores;"
```

Esperado:

```text
120000
```

### Gateways

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM gateways;"
```

Esperado:

```text
32
```

### Medidores con coordenadas

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT medidor_id, mac, numero_serie, distrito_id, zona_id, categoria_tarifa, gateway_id, latitud, longitud, estado FROM medidores LIMIT 10;"
```

### Historial de medidores

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT medidor_id, numero_serie, estado, motivo_estado, medidor_anterior_id, es_medidor_actual, fecha_instalacion, fecha_retiro FROM medidores LIMIT 10;"
```

---

## ⚠️ Nota sobre `COUNT(*)` en lecturas

En Cassandra no se recomienda validar tablas grandes con:

```sql
SELECT COUNT(*) FROM lecturas_por_medidor;
```

Puede dar timeout porque Cassandra debe recorrer muchas particiones.

Para verificar lecturas usar:

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT * FROM lecturas_por_medidor LIMIT 5;"
```

Y:

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT * FROM lecturas_por_zona_dia LIMIT 5;"
```

O estadísticas:

```powershell
docker exec semapa-cassandra-1 nodetool tablestats semapa lecturas_por_medidor
```

---

## 🌐 URLs y puertos

| Servicio | URL / Puerto |
|---|---|
| Frontend | `http://localhost` |
| Mapa | `http://localhost/mapa` |
| API Swagger | `http://localhost/api/v1/docs` |
| Mailhog | `http://localhost:8025` |
| RabbitMQ UI | `http://localhost:15672` |
| Cassandra CQL | `localhost:9042` |
| Redis | `localhost:6379` |

---

## 🔑 Credenciales de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Alcaldía | `alcaldia` | `Alcaldia2025!` |
| Gerencia | `gerencia` | `Gerencia2025!` |
| Contabilidad | `contabilidad` | `Contab2025!` |

---

## 🌐 Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login y JWT. |
| `GET` | `/api/v1/dashboard/kpis` | KPIs generales. |
| `GET` | `/api/v1/mapa/resumen` | Resumen territorial del mapa. |
| `GET` | `/api/v1/mapa/zonas` | Zonas/distritos para burbujas. |
| `GET` | `/api/v1/mapa/gateways` | Gateways/radiobases. |
| `GET` | `/api/v1/mapa/medidores-sample` | Muestra de medidores georreferenciados. |
| `GET` | `/api/v1/consultas/...` | Consultas estratégicas. |
| `GET` | `/api/v1/buscar?q=...` | Buscador por contrato, MAC, serie o cliente. |
| `POST` | `/api/v1/facturas/generar` | Generación de facturas. |
| `POST` | `/api/v1/notify` | Envío por email/SMS/WhatsApp. |

Si el endpoint responde:

```json
{"detail":"Falta token"}
```

significa que la API está funcionando, pero requiere autenticación.

---

## 🧪 Login por PowerShell para probar API

```powershell
$login = curl.exe -s -X POST http://localhost/api/v1/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"gerencia\",\"password\":\"Gerencia2025!\"}" | ConvertFrom-Json

$TOKEN = $login.access_token
```

Probar mapa:

```powershell
curl.exe http://localhost/api/v1/mapa/resumen -H "Authorization: Bearer $TOKEN"
```

---

## 🧩 Datos simulados y justificación

Los datos son **sintéticos**, no son datos reales de clientes de SEMAPA.

Se generaron siguiendo la consigna:

```text
80.000 personas naturales
5.000 personas jurídicas
100.000 infraestructuras
120.000 medidores
32 gateways
9 categorías tarifarias
```

Relación defendible:

```text
persona → infraestructura / contrato → medidores
```

Una persona puede tener varios medidores porque puede tener varias infraestructuras, un edificio/condominio, varios contratos o historial de reemplazo. Los medidores anteriores no se eliminan: quedan como históricos con `medidor_anterior_id`, `fecha_retiro`, `motivo_estado` y `es_medidor_actual`.

---

## 🧑‍💻 Responsabilidad de Denis

Responsabilidad principal:

```text
Seeder
Datos base
Distribución territorial
Georreferenciación
Mapa como evidencia visual
```

Lo que debe defender:

```text
- Cómo se generaron 85.000 personas.
- Cómo se generaron 100.000 infraestructuras.
- Cómo se generaron 120.000 medidores.
- Por qué una persona puede tener varios medidores.
- Cómo se asignaron distrito, zona, tarifa, gateway y coordenadas.
- Por qué se repararon coordenadas para que queden dentro de Cercado.
- Cómo el mapa demuestra burbujas, calor, puntos y filtros.
```

Frase recomendada:

> “Mi módulo se encarga del poblamiento masivo y la georreferenciación. Los datos son sintéticos, pero respetan las cantidades y reglas de la práctica. Cada medidor tiene distrito, zona, tarifa, gateway, estado y coordenadas. Además, se incorporó una reparación geográfica para garantizar que los datos se visualicen solo dentro del municipio Cercado.”

---

## 🧯 Problemas comunes

### El mapa no actualiza

```powershell
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

Luego en el navegador:

```text
Ctrl + F5
```

### El build de frontend falla por registry npm

Reemplazar registry interno en `web/package-lock.json`:

```powershell
(Get-Content .\web\package-lock.json -Raw) `
  -replace 'https://packages\.applied-caas-gateway1\.internal\.api\.openai\.org/artifactory/api/npm/npm-public/', 'https://registry.npmjs.org/' |
  Set-Content .\web\package-lock.json -Encoding UTF8
```

Verificar:

```powershell
Select-String -Path .\web\package-lock.json -Pattern "applied-caas"
```

### La carga de lecturas tarda demasiado

No ejecutar sin variables:

```powershell
docker compose run --rm seeder python seed_lecturas.py
```

Usar demo:

```powershell
docker compose run --rm -e LECTURAS_LIMITE_MEDIDORES=5000 -e LECTURAS_STEP_DIAS=7 -e LECTURAS_POR_DIA=1 seeder python seed_lecturas.py
```

### `SELECT COUNT(*)` falla en lecturas

Es normal en Cassandra para tablas grandes. Usar `LIMIT` o `nodetool tablestats`.

---

## 📦 Comando final recomendado para entregar

```powershell
docker compose build web api-1 api-2 seeder
docker compose up -d
docker compose run --rm seeder python repair_geo.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

Abrir:

```text
http://localhost/mapa
```

---

## 📄 Licencia

Uso académico — Práctica 5 Cassandra, Sistemas Distribuidos.
