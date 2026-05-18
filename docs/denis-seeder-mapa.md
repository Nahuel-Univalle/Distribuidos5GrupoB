# Guía de trabajo de Denis Almaquio: seeder + georreferenciación + mapa

## Qué se corrigió

1. La hoja `Distritos` se interpreta como distribución de **100.000 infraestructuras/servicios base**.
2. El seeder genera exactamente:
   - 80.000 personas naturales.
   - 5.000 personas jurídicas.
   - 100.000 infraestructuras.
   - 120.000 medidores.
3. La diferencia entre 100.000 infraestructuras y 120.000 medidores se modela con historial:
   - medidor viejo reemplazado,
   - medidor dañado,
   - medidor retirado,
   - cambio a IoT,
   - segunda toma en la misma infraestructura.
4. El modelo queda defendible como:

```text
persona -> infraestructura/servicio -> medidores actuales e históricos
```

5. Se corrigió el tipo de infraestructura: ya no se inserta `tipo_infra = 0`; ahora se usan tipos 1..12.
6. Se expande el Excel de 4 radiobases principales a **32 gateways simulados**: 8 sectores LoRaWAN por radiobase.
7. Se agregó un mapa web propio con OpenStreetMap + GeoJSON aproximado generado desde `data/seeds/zonas.csv`; esto evita depender de descargar el mapa municipal.
8. Se agregaron endpoints API para el mapa:
   - `GET /api/v1/mapa/resumen`
   - `GET /api/v1/mapa/zonas`
   - `GET /api/v1/mapa/gateways`
   - `GET /api/v1/mapa/medidores-sample`
9. El generador de lecturas queda alineado con la consigna:
   - desde `2025-04-01`,
   - 3 lecturas por día,
   - todos los días por defecto.

## Comandos recomendados

```bash
cp .env.example .env
docker compose up -d cassandra-1 cassandra-2 cassandra-init redis rabbitmq mailhog

docker compose run --rm seeder python seed.py

# Por defecto ahora es rápido: LECTURAS_PRESET=demo
# Carga una muestra estratificada suficiente para dashboard, mapa y consultas.
docker compose run --rm seeder python seed_lecturas.py
```

Presets disponibles para lecturas:

```bash
# Rápido, recomendado para defensa: aprox. 150.000 lecturas y escritura en 2 tablas.
docker compose run --rm -e LECTURAS_PRESET=demo seeder python seed_lecturas.py

# Muestra media para exposición.
docker compose run --rm -e LECTURAS_PRESET=exposicion seeder python seed_lecturas.py

# Completo real: todos los medidores, todos los días, 3 lecturas por día.
# Puede tardar horas; usar solo si hay tiempo/máquina fuerte.
docker compose run --rm -e LECTURAS_PRESET=full -e LECTURAS_CONFIRMAR_FULL=SI seeder python seed_lecturas.py
```

Luego levantar todo:

```bash
docker compose up -d
```


## Criterio de carga rápida de lecturas

La consigna completa pide 3 lecturas por día desde `2025-04-01` para todos los medidores. Al ejecutarlo en 2026, eso puede superar 100 millones de lecturas y duplicarse porque se insertan en dos tablas Cassandra. Para una laptop de defensa se usa `LECTURAS_PRESET=demo`, que conserva la lógica del sistema pero carga una muestra estratificada por zona/tarifa/medidor.

La defensa debe explicar que Cassandra soporta la carga completa, pero para demostrar API, dashboard, mapa y consultas se usa un preset reducido para no esperar horas durante la presentación.

## Verificación en Cassandra

```bash
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM personas;"
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM infraestructuras;"
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM medidores;"
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM gateways;"
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; SELECT COUNT(*) FROM tarifas;"
```

Resultados esperados:

```text
personas = 85.000
infraestructuras = 100.000
medidores = 120.000
gateways = 32
tarifas = 9
```

## Qué explicar en defensa

> El Excel trae 100.000 registros distribuidos por zona y tarifa. En el proyecto se tratan como infraestructuras o servicios base. Sobre esas infraestructuras se generan 120.000 medidores porque una persona o infraestructura puede tener más de un medidor por reemplazo, antigüedad, daño, retiro, cambio a IoT o múltiples puntos de consumo. No se borra el medidor antiguo; queda como histórico.

## Mapa

El enlace municipal `mapadigital.cochabamba.bo` sirve para validar visualmente capas administrativas, pero no fue necesario descargarlo. El sistema usa:

- OpenStreetMap como mapa base.
- `web/src/data/cochabambaZonas.ts` como GeoJSON aproximado de 54 zonas.
- API `/mapa/*` para estadísticas reales desde Cassandra.

