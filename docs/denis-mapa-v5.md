# Ajustes v5 — Mapa georreferenciado SEMAPA

Cambios realizados para la defensa de georreferenciación:

- El mapa ahora ocupa todo el ancho disponible para que no se vea apretado.
- El panel de análisis lateral se puede ocultar y mostrar.
- Las capas municipales WMS se controlan desde un botón flotante de “Capas”.
- Se agregó botón para apagar todas las capas WMS municipales.
- Capas disponibles: zonas SEMAPA locales, distritos, comunas, subdistritos, límite Cercado, área urbana y manzanas.
- Los centroides visuales de zonas se ajustaron para respetar mejor la ubicación aproximada de los distritos según las capturas del mapa municipal.
- Los puntos de medidores se dibujan visualmente dentro de su zona/distrito usando el vínculo distrito-zona del dato; esto evita que la muestra aparezca fuera del distrito por coordenadas sintéticas demasiado dispersas.
- Se conserva la advertencia técnica: no son polígonos oficiales descargados; las capas WMS municipales sirven como validación visual.

Comandos:

```powershell
docker compose build web
docker compose up -d
```

Si el navegador muestra la versión vieja:

```powershell
docker compose restart web nginx
```

Luego recargar con Ctrl+F5.
