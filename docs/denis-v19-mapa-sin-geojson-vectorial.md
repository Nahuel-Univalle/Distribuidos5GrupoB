# Denis v19 - Mapa sin capa GeoJSON vectorial visible

## Cambio realizado

Se desactivó por defecto la capa `Distritos GeoJSON vectorial` porque dibujaba líneas rosadas adicionales que confundían la lectura del mapa.

## Estado nuevo del mapa

- La capa GeoJSON vectorial queda cargada internamente solo como apoyo para validación/máscara, pero no se muestra en el mapa.
- La capa visible de distritos queda como `Distritos municipales` mediante WMS.
- Se mantiene `Límite Cercado` activo.
- Se mantiene `Fuera de Cercado en gris` activo.
- El panel de capas ya no expone el GeoJSON vectorial como opción principal.

## Archivo modificado

```text
web/src/pages/Mapa.tsx
```

## Líneas clave

```tsx
const [showGeoJsonDistritos, setShowGeoJsonDistritos] = useState(false);
const [showDistritos, setShowDistritos] = useState(true);
```

## Aplicación

```powershell
docker compose build web
docker compose up -d
docker compose restart web nginx
```

Luego abrir:

```text
http://localhost/mapa
```

y presionar `Ctrl + F5`.
