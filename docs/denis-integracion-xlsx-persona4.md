# Denis — Integración con XLSX nuevo y API Persona 4

Este documento resume los cambios aplicados para dejar el módulo de **poblamiento, georreferenciación y mapa** listo para conectarse con la parte de **Backend API + Consultas Estratégicas**.

## 1. XLSX actualizado

El archivo de recursos actual se mantiene en la raíz del proyecto como:

```text
Recursos Practica 5.xlsx
```

El `docker-compose.yml` lo monta dentro del contenedor seeder como:

```text
/recursos/recursos.xlsx
```

El XLSX nuevo agrega hojas como:

```text
Infraestructura
Catastro
Contratos
Lecturas
Medidores
```

La hoja principal para el poblamiento territorial sigue siendo:

```text
Distritos
```

Esa hoja contiene la distribución base de **100.000 infraestructuras** por subalcaldía, distrito, zona/subdistrito y categoría tarifaria.

## 2. Archivos actualizados de mi parte

```text
services/seeder/excel_loader.py
```

Ahora soporta el XLSX nuevo. La hoja `Distritos` ya no se lee por posición fija; se detectan columnas por cabecera (`R1`, `R2`, `R3`, `R4`, `C`, `CE`, `I`, `P`, `S`, `HABITANTES`, `TOTAL`). Esto evita que se desordenen los conteos cuando el Ing. agrega columnas auxiliares.

```text
services/seeder/geo_reference.py
```

Mantiene la referencia territorial por clave compuesta:

```text
distrito_id + zona_id
```

No se usa solo `zona_id`, porque en la práctica hay zonas repetidas en distintos distritos.

```text
services/seeder/repair_geo.py
```

Corrige coordenadas ya cargadas en Cassandra sin borrar datos. Repara:

```text
infraestructuras
medidores
gateways/radiobases
```

```text
services/api/app/routers/mapa.py
```

Entrega datos geográficos seguros al frontend y evita pintar puntos fuera de Cercado.

```text
web/src/pages/Mapa.tsx
```

Dashboard territorial para defensa del módulo Denis: burbujas, calor, puntos, filtros, capas y resumen.

## 3. Integración con Persona 4 / Cristian

Se mantuvieron los endpoints descriptivos propios, por ejemplo:

```text
/api/v1/consultas/medidores-activos
/api/v1/consultas/zonas-anomalas
/api/v1/consultas/cobertura-antenas
```

Y se agregaron rutas numéricas compatibles con la parte de Persona 4:

```text
/api/v1/consultas/1
/api/v1/consultas/2
...
/api/v1/consultas/25
```

También se agregó compatibilidad legacy con la ruta que aparecía en la rama de Cristian:

```text
/api/v1/consultas/consultas/1
```

Así, si el frontend o Postman de Persona 4 llama las consultas por número, no debería romperse.

## 4. Documentación de Persona 4 importada

Se copiaron estos documentos como respaldo sin pisar la documentación de Denis:

```text
docs/API_TECNICA_PERSONA4.md
docs/EJEMPLOS_CURL_PERSONA4.sh
docs/README_BACKEND_PERSONA4.md
docs/SEMAPA_API_PERSONA4.postman_collection.json
```

## 5. Comandos recomendados

Levantar y compilar:

```powershell
docker compose build web api-1 api-2 seeder
docker compose up -d
```

Reparar coordenadas después del seed o al cambiar el XLSX:

```powershell
docker compose run --rm seeder python repair_geo.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

Lecturas demo, no usar el modo completo en laptop:

```powershell
docker compose run --rm -e LECTURAS_LIMITE_MEDIDORES=5000 -e LECTURAS_STEP_DIAS=7 -e LECTURAS_POR_DIA=1 seeder python seed_lecturas.py
```

## 6. Verificaciones esperadas

El loader del XLSX nuevo debe mostrar:

```text
15 distritos
54 zonas
100000 total base
9 tarifas
5 modelos de medidor
9 errores IoT
```

El repair geográfico debe terminar con algo similar a:

```text
Coordenadas reparadas: 100000 infraestructuras, 120000 medidores y 32 gateways
Validación interna: fuera_de_cercado infra=0 medidores=0 gateways=0
```

## 7. Defensa de mi parte

> Mi módulo se encarga del poblamiento masivo y georreferenciación. El XLSX nuevo se usa como fuente de distribución territorial y tarifas. La visualización del mapa no era mi responsabilidad principal, pero se implementó como apoyo para demostrar que los medidores, infraestructuras y gateways quedan dentro del municipio Cercado, filtrados por distrito, zona, tarifa, estado y gateway. Además, se dejó compatibilidad con la API de consultas de la Persona 4 mediante rutas numéricas `/api/v1/consultas/1..25`.
