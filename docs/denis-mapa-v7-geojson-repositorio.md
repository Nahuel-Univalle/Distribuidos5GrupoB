# Mapa SEMAPA v7 — integración GeoJSON oficial externo

Esta versión mejora la pantalla de mapa para la defensa de poblamiento y georreferenciación.

## Cambios aplicados

- Se integra el repositorio público `ciudatoslab/20-distritos-en-cochabamba` como fuente vectorial de distritos.
- El frontend carga `distritos_cbba-2.geojson` y normaliza sus coordenadas.
- Si el GeoJSON llega en UTM zona 19S, el frontend lo transforma a latitud/longitud para Leaflet.
- Los polígonos vectoriales se usan como capa principal para la ubicación visual de distritos.
- Las burbujas y puntos se anclan dentro del distrito municipal usando la geometría oficial cuando está disponible.
- Las capas WMS municipales quedan como respaldo visual y se pueden apagar/encender individualmente.
- La capa local de zonas SEMAPA queda opcional para no tapar ni confundir el mapa municipal.

## Capas disponibles

- Distritos GeoJSON vectorial del repositorio.
- Distritos WMS municipal.
- Comunas WMS municipal.
- Subdistritos WMS.
- Límite Cercado WMS.
- Área urbana WMS.
- Manzanas WMS.
- Zonas SEMAPA generadas.

## Defensa sugerida

> Para evitar que las burbujas queden ubicadas solo por coordenadas aproximadas, integramos una capa vectorial GeoJSON de distritos de Cochabamba. El sistema usa esa geometría para ubicar visualmente los datos generados por el seeder, y mantiene las capas WMS municipales como respaldo visual ocultable. Los datos de negocio siguen viniendo de Cassandra: medidores, infraestructuras, gateways, tarifas, estados y consumos.
