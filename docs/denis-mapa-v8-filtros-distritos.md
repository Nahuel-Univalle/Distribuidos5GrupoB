# Corrección v8: mapa, filtros y capas

Esta versión corrige la visualización del mapa territorial para la defensa del módulo de Denis Hamilton Almaquio.

## Cambios principales

- Las burbujas y puntos ya no se reubican usando solamente `zona_id`, porque el Excel reutiliza algunos IDs de zona en distintos distritos. Ahora la ubicación visual se respeta por la clave compuesta `distrito_id + zona_id`.
- Al filtrar por distrito, las burbujas, puntos, mapa de calor y resumen filtrado usan el distrito del seeder/Excel.
- El panel de capas pasó al lado derecho.
- Se agregó una guía vectorial de distritos SEMAPA que no desaparece al hacer zoom.
- Las capas WMS municipales siguen siendo opcionales y ocultables: distritos, comunas, subdistritos, límite Cercado, área urbana y manzanas.
- El mapa crece en altura para que no se vea apretado.

## Nota para exposición

La fuente de verdad de poblamiento es el Excel de la práctica cargado por el seeder. Las capas municipales se usan como referencia visual. Para evitar errores por IDs de zona repetidos, el frontend trabaja con la combinación distrito-zona y no solamente con el número de zona.

