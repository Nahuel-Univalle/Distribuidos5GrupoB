# Ajuste v11 - Mapa solo municipio Cercado

## Objetivo

El mapa de la parte de Denis debe representar únicamente el municipio de Cercado/Cochabamba. Cualquier punto, burbuja o zona fuera del límite de Cercado no debe aparecer como dato SEMAPA.

## Cambios aplicados

- El frontend agrega una máscara visual: fuera de Cercado se muestra en gris.
- Solo Cercado queda destacado con capas de distritos/zonas, burbujas, puntos y mapa de calor.
- El botón `Capas` incluye la opción `Fuera de Cercado en gris`.
- Los endpoints geográficos de la API filtran por distritos 1..15.
- Las burbujas, puntos y heatmap vuelven a validarse contra el GeoJSON de distritos cuando está disponible.
- Si el GeoJSON externo no carga, se usa un polígono aproximado de respaldo para Cercado.

## Comandos de aplicación

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

y presionar `Ctrl + F5`.

## Para defensa

> El módulo de georreferenciación trabaja solo sobre el municipio de Cercado. Los datos se filtran por sus distritos 1 al 15, y el mapa muestra el exterior en gris para evitar confundir datos de otros municipios como Tiquipaya, Colcapirhua, Sacaba o Quillacollo. Las capas WMS/GeoJSON sirven como referencia visual, pero los datos SEMAPA provienen de Cassandra y del seeder corregido.
