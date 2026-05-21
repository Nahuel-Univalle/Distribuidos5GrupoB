# V12 — Seeder estricto para municipio Cercado

Esta versión corrige el problema visual donde algunos medidores o burbujas aparecían fuera del límite gris del municipio Cercado o fuera del distrito que indicaba el filtro.

## Cambios principales

- `services/seeder/geo_reference.py` se volvió la fuente única de ubicación.
- Las coordenadas se generan por clave compuesta `distrito_id + zona_id`, nunca por `zona_id` solamente.
- Se redujo el radio de dispersión para no cruzar límites distritales.
- Se agregó validación `is_inside_cercado()` para que los puntos no salgan del municipio Cercado.
- `services/seeder/repair_geo.py` repara coordenadas ya cargadas sin modificar cantidades, personas, contratos ni tarifas.
- `services/api/app/routers/mapa.py` ignora puntos fuera de Cercado aunque existan en Cassandra.
- `web/src/pages/Mapa.tsx` usa una máscara gris más estricta fuera de Cercado y aplica el filtro aun cuando el GeoJSON externo no cargue.

## Comandos recomendados

Para corregir la base ya cargada:

```powershell
docker compose build web api-1 api-2 seeder
docker compose up -d
docker compose run --rm seeder python repair_geo.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

Luego abrir:

```text
http://localhost/mapa
```

Y recargar fuerte:

```text
Ctrl + F5
```

## Si se quiere regenerar todo desde cero

Usar solo si se desea borrar y volver a poblar:

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; TRUNCATE lecturas_raw; TRUNCATE lecturas_por_medidor; TRUNCATE lecturas_por_zona_dia; TRUNCATE cobertura_gateway; TRUNCATE facturas; TRUNCATE facturas_por_periodo; TRUNCATE medidores; TRUNCATE infraestructuras; TRUNCATE personas; TRUNCATE usuarios_sistema; TRUNCATE distritos; TRUNCATE zonas; TRUNCATE gateways; TRUNCATE modelos_medidor; TRUNCATE tarifas; TRUNCATE errores_iot; TRUNCATE tipos_infraestructura; TRUNCATE sub_alcaldias;"
docker compose run --rm seeder python seed.py
docker compose run --rm -e LECTURAS_LIMITE_MEDIDORES=5000 -e LECTURAS_STEP_DIAS=7 -e LECTURAS_POR_DIA=1 seeder python seed_lecturas.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

## Explicación para defensa

> El sistema trabaja únicamente el municipio Cercado. Por eso se corrigió el seeder para generar coordenadas dentro de sus 15 distritos. La distribución sigue viniendo del Excel de la práctica, pero la ubicación se normaliza usando la clave compuesta distrito-zona. Esto evita que una zona repetida o una coordenada dispersa se dibuje fuera del distrito o fuera de Cercado.
