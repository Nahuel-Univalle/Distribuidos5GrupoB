# Frontend actualizado para defensa de la parte de Denis

Este ajuste deja el frontend preparado para demostrar el módulo de **poblamiento masivo, distribución territorial y georreferenciación**.

## Pantallas tocadas

- `web/src/pages/Mapa.tsx`
- `web/src/pages/Dashboard.tsx`
- `web/src/components/Layout.tsx`
- `web/src/pages/Login.tsx`
- `web/src/index.css`
- `web/src/vite-env.d.ts`

## Qué demuestra el mapa

El mapa ahora permite mostrar:

- 100.000 infraestructuras.
- 120.000 medidores.
- 32 gateways/radiobases.
- 54 zonas territoriales del Excel.
- Medidores por estado operativo.
- Medidores por categoría tarifaria.
- Medidores por distrito y zona.
- Medidores por gateway.
- Búsqueda dentro de la muestra por contrato, MAC, serie o UUID.
- Mapa de calor.
- Burbujas por zona.
- Puntos individuales de medidores.
- Histograma por hora.
- Capas WMS municipales: distritos, comunas, subdistritos y límite Cercado.

## Filtros disponibles

- Estado: TODOS, ACTIVO, INACTIVO, FUERA_SERVICIO, REEMPLAZADO, DAÑADO, RETIRADO.
- Tarifa: R1, R2, R3, R4, C, CE, I, P, S.
- Distrito.
- Zona.
- Gateway.
- Capa analítica: mixto, calor, burbujas, puntos.
- Métrica: consumo, medidores, activos, fallas.
- Tamaño de muestra: 1.000, 2.500, 4.000, 8.000, 10.000.
- Buscador: contrato, MAC, serie o UUID.

## Explicación sugerida

> Mi parte no consiste principalmente en desarrollar todo el frontend. Sin embargo, actualicé el dashboard y el mapa para demostrar visualmente el resultado de mi módulo de datos. El mapa consume los datos cargados en Cassandra por el seeder: personas, infraestructuras, medidores, estados, tarifas, gateways y coordenadas. Además, el mapa incluye calor, burbujas, puntos individuales, filtros y capas municipales WMS para validar la ubicación territorial.

## Comandos

```powershell
docker compose up -d --build
```

Abrir:

```text
http://localhost
```

Credenciales de prueba:

```text
alcaldia / Alcaldia2025!
gerencia / Gerencia2025!
contabilidad / Contab2025!
```

## Prueba de compilación

El frontend fue probado con:

```bash
npm run build
```

Resultado: compilación correcta.
