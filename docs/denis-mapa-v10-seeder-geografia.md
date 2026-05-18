# Corrección v10 — seed geográfico + filtros reales del mapa

Esta versión corrige dos problemas detectados en la defensa visual:

1. Algunos puntos/burbujas se veían fuera del distrito porque el seed inicial usaba coordenadas con dispersión amplia y centros incompletos.
2. Al aplicar filtros, algunas burbujas agregadas seguían visibles aunque no correspondían al filtro.

## Cambios técnicos

- Se agregó `services/seeder/geo_reference.py` como fuente única de centros por `(distrito_id, zona_id)`.
- `seed.py` ahora genera coordenadas nuevas usando esos centros y una dispersión pequeña.
- `repair_geo.py` repara datos ya existentes en Cassandra sin borrar personas, contratos ni medidores.
- `/api/v1/mapa/zonas` ahora acepta filtros: `estado`, `categoria`, `distrito_id`, `zona_id`, `gateway_id`.
- El frontend consulta `/mapa/zonas` con los filtros activos.
- Si una zona queda con `medidores=0` después de filtrar, no se dibuja su burbuja.
- Si se busca por contrato, MAC, serie o UUID, se ocultan las burbujas agregadas y se muestran solo puntos coincidentes.

## Aplicar sin borrar datos existentes

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

y hacer `Ctrl + F5`.

## Rehacer seed completo desde cero

Solo usar si quieres borrar los datos existentes y generar todo nuevamente con el seed corregido:

```powershell
docker exec semapa-cassandra-1 cqlsh -e "USE semapa; TRUNCATE lecturas_raw; TRUNCATE lecturas_por_medidor; TRUNCATE lecturas_por_zona_dia; TRUNCATE cobertura_gateway; TRUNCATE facturas; TRUNCATE facturas_por_periodo; TRUNCATE medidores; TRUNCATE infraestructuras; TRUNCATE personas; TRUNCATE usuarios_sistema; TRUNCATE distritos; TRUNCATE zonas; TRUNCATE gateways; TRUNCATE modelos_medidor; TRUNCATE tarifas; TRUNCATE errores_iot; TRUNCATE tipos_infraestructura; TRUNCATE sub_alcaldias;"
docker compose run --rm seeder python seed.py
docker compose run --rm -e LECTURAS_LIMITE_MEDIDORES=5000 -e LECTURAS_STEP_DIAS=7 -e LECTURAS_POR_DIA=1 seeder python seed_lecturas.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

## Explicación para defensa

La corrección clave es que la ubicación no se calcula por `zona_id` solo, porque el Excel repite códigos de zona en distintos distritos. La clave correcta es `(distrito_id, zona_id)`. Además, el mapa usa filtros reales desde backend, por lo tanto si una burbuja no corresponde al filtro activo no se dibuja.
