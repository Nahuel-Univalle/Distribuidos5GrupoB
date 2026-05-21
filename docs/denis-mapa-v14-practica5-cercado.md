# Versión Denis v14 — Georreferenciación ajustada a Práctica 5

Esta versión actualiza el módulo de Denis usando la información nueva de la presentación de la Práctica 5.

## Fuente territorial usada

La referencia principal ya no es una distribución visual aproximada, sino el árbol territorial de la práctica:

`SubAlcaldía → Distrito → Subdistrito/Zona`

Se trabaja solamente el **municipio Cercado de Cochabamba**, con los distritos 1 al 15 y las zonas/subdistritos indicados por la práctica.

## Archivos modificados

- `services/seeder/geo_reference.py`
- `services/seeder/excel_loader.py`
- `services/seeder/repair_geo.py`
- `services/api/app/routers/mapa.py`
- `web/src/pages/Mapa.tsx`

## Qué corrige

1. El seeder genera coordenadas por clave compuesta `distrito_id + zona_id`.
2. La API ya no devuelve coordenadas antiguas fuera de Cercado para el mapa; si Cassandra conserva coordenadas viejas, las normaliza visualmente con referencia segura.
3. `repair_geo.py` repara infraestructuras, medidores y gateways.
4. El frontend filtra burbujas, puntos y mapa de calor por estado, tarifa, distrito, zona, gateway y búsqueda.
5. Fuera del municipio Cercado se muestra en gris, y los datos SEMAPA se pintan solo dentro de Cercado.
6. Las capas municipales WMS y GeoJSON se mantienen como respaldo visual ocultable.

## Comandos recomendados

```powershell
docker compose build web api-1 api-2 seeder
docker compose up -d
docker compose run --rm seeder python repair_geo.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

Después abre:

```text
http://localhost/mapa
```

Y presiona `Ctrl + F5`.

## Si se quiere regenerar todo desde cero

Solo si se desea borrar y poblar nuevamente:

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; TRUNCATE lecturas_raw; TRUNCATE lecturas_por_medidor; TRUNCATE lecturas_por_zona_dia; TRUNCATE cobertura_gateway; TRUNCATE facturas; TRUNCATE facturas_por_periodo; TRUNCATE medidores; TRUNCATE infraestructuras; TRUNCATE personas; TRUNCATE usuarios_sistema; TRUNCATE distritos; TRUNCATE zonas; TRUNCATE gateways; TRUNCATE modelos_medidor; TRUNCATE tarifas; TRUNCATE errores_iot; TRUNCATE tipos_infraestructura; TRUNCATE sub_alcaldias;"
docker compose run --rm seeder python seed.py
docker compose run --rm -e LECTURAS_LIMITE_MEDIDORES=5000 -e LECTURAS_STEP_DIAS=7 -e LECTURAS_POR_DIA=1 seeder python seed_lecturas.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

## Explicación para defensa

> Mi módulo trabaja el poblamiento masivo y la georreferenciación. Se usa solamente el municipio Cercado, con el árbol territorial de la práctica: subalcaldía, distrito y zona/subdistrito. La clave de ubicación es compuesta: distrito_id + zona_id, porque varios zona_id se repiten en distintos distritos. Las coordenadas se generan dentro de centros seguros por zona y se repara la base para evitar puntos fuera de Cercado. El mapa mantiene capas WMS/GeoJSON como respaldo visual, pero los datos SEMAPA se pintan solo dentro del área de Cercado.
