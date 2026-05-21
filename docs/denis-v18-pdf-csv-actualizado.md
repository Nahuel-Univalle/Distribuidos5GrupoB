# Denis — Actualización v18 por PDF y CSV nuevos

## Motivo

El PDF actualizado de la Práctica 5 cambia el enfoque hacia una **Plataforma de Big Data Distribuida** para SEMAPA. Para el módulo de Denis se ajustó el poblamiento a los nuevos recursos exportados del Excel.

## Nuevas cantidades de trabajo

Según el PDF actualizado, el módulo de datos debe trabajar con:

- 80.000 infraestructuras.
- 100.000 contratos.
- 120.000 medidores IoT.
- 100.000 lecturas por 3 meses: febrero, marzo y abril.
- 9 categorías tarifarias.
- 14 radiobases LoRaWAN.
- 54 subdistritos / zonas.

> Nota: el documento tiene una contradicción menor porque en una sección menciona 80.000 infraestructuras y en otra 100.000. Esta versión deja `SEED_TARGET_INFRA=80000` por defecto, pero el valor puede cambiarse por variable de entorno.

## CSV incorporados

Los archivos se guardaron en:

```text
data/external/infraestructuras_cochabamba.csv
data/external/contratos_agua.csv
data/external/medidores_iot.csv
data/external/lecturas_iot.csv
```

## Seeders actualizados

### `services/seeder/external_sources.py`

Nuevo módulo que lee y normaliza los CSV del Excel actualizado:

- tolera UTF-8 y latin-1;
- normaliza MACs;
- convierte contrato `CT-00000001` a `1` para la columna bigint;
- normaliza fechas de instalación al rango 2020-01-01 a 2025-03-01;
- mapea estados de medidor: Operativo, Nuevo, Mantenimiento, Reacondicionado, Dañado;
- mapea categorías tarifarias R1, R2, R3, R4, C, CE, I, P, S.

### `services/seeder/seed.py`

Ahora usa los CSV cuando existen:

- inserta 80.000 infraestructuras desde el CSV;
- inserta 100.000 contratos desde el CSV;
- inserta 120.000 medidores desde el CSV;
- los 100.000 medidores asociados a contrato quedan conectados por `numero_contrato`;
- los 20.000 medidores restantes quedan como históricos, reemplazados, mantenimiento o fuera de servicio;
- mantiene coordenadas dentro del municipio Cercado usando `geo_reference.py`;
- usa 14 radiobases, no 32.

### `services/seeder/seed_lecturas.py`

Ahora intenta usar primero:

```text
data/external/lecturas_iot.csv
```

Ese CSV trae lecturas de febrero, marzo y abril. Si no existe, usa el modo sintético anterior con presets.

### `services/seeder/excel_loader.py`

Se ajustó para leer la hoja `Distritos` por encabezados y no por posición fija, porque el Excel nuevo agregó columnas intermedias.

### `infra/cassandra/init/02_tables.cql`

Se agregó tabla de contratos:

```sql
contratos
contratos_por_estado
```

Esto deja la base preparada para Persona 4 y sus consultas de contratos activos, suspendidos, mora y preavisos.

## Comandos recomendados

### Limpiar datos anteriores si se duplicaron

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; TRUNCATE lecturas_raw; TRUNCATE lecturas_por_medidor; TRUNCATE lecturas_por_zona_dia; TRUNCATE cobertura_gateway; TRUNCATE facturas; TRUNCATE facturas_por_periodo; TRUNCATE contratos; TRUNCATE contratos_por_estado; TRUNCATE medidores; TRUNCATE infraestructuras; TRUNCATE personas; TRUNCATE usuarios_sistema; TRUNCATE distritos; TRUNCATE zonas; TRUNCATE gateways; TRUNCATE modelos_medidor; TRUNCATE tarifas; TRUNCATE errores_iot; TRUNCATE tipos_infraestructura; TRUNCATE sub_alcaldias;"
```

### Poblar base con CSV nuevo

```powershell
docker compose run --rm seeder python seed.py
```

### Reparar coordenadas por seguridad

```powershell
docker compose run --rm seeder python repair_geo.py
```

### Cargar lecturas del CSV nuevo

```powershell
docker compose run --rm seeder python seed_lecturas.py
```

### Limpiar caché y reiniciar

```powershell
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

## Validación esperada

```text
infraestructuras = 80.000
contratos = 100.000
medidores = 120.000
gateways = 14
tarifas = 9
lecturas ≈ 297.000 a 303.000 según CSV útil
```

## Relación de datos

```text
persona → infraestructura → contrato → medidor IoT → lecturas
```

También se mantiene historial de medidores porque existen medidores sin contrato activo, reacondicionados, dañados o en mantenimiento.

## Listo para integración

No se integró la rama de Persona 4. Solo se dejaron las tablas, datos y documentación listos para que Persona 1 integre los endpoints de consultas estratégicas sin pisar el seeder de Denis.
