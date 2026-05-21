# Denis — Seeders actualizados para el XLSX nuevo

Esta versión deja la parte de poblamiento/geodatos lista para trabajar con `03 Practica 5 Recursos.xlsx`.

## Hojas soportadas

El loader `services/seeder/excel_loader.py` ahora reconoce y valida estas hojas:

- `Distritos`: distribución territorial por SubAlcaldía, Distrito, Subdistrito/Zona y cuotas R1, R2, R3, R4, C, CE, I, P, S.
- `Infraestructura`: plantillas catastrales, direcciones, uso de suelo, manzano/lote y datos referenciales.
- `Catastro`: referencia del formato `distrito-zona-manzano-lote-subdivisión`.
- `Contratos`: plantillas de contrato, estado, subcategoría, diámetro y tipo de servicio.
- `Medidores`: plantillas de MAC, fecha, estado y tipo/modelo.
- `Lecturas`: plantillas de lectura anterior/actual, radiobase y fecha de pago.
- `UnidadesEducativas`, `InfraestrucuraPublicas`, `Tarifario`, `ErroresIOT`, `ModeloMedidores`.

## Reglas aplicadas

- Se usa solo municipio Cercado.
- La clave geográfica es siempre `(distrito_id, zona_id)`, nunca `zona_id` sola.
- La hoja `Distritos` se lee por encabezados `R1..S`, no por posiciones rígidas antiguas.
- La distribución base sigue sumando `100.000` infraestructuras.
- Se generan `120.000` medidores.
- Las coordenadas se toman desde `geo_reference.py`, no desde muestras del Excel, para evitar puntos fuera de Cercado.
- `repair_geo.py` corrige infraestructuras, medidores y gateways ya cargados.
- `seed_lecturas.py` valida la hoja `Lecturas` y genera la serie histórica masiva o demo.

## Archivos modificados

```text
services/seeder/excel_loader.py
services/seeder/seed.py
services/seeder/seed_lecturas.py
services/seeder/repair_geo.py
data/seeds/*.csv
Recursos Practica 5.xlsx
README.md
```

## Comandos recomendados

Construir:

```powershell
docker compose build web api-1 api-2 seeder
```

Levantar:

```powershell
docker compose up -d
```

Si ya existe la base y solo quieres corregir coordenadas:

```powershell
docker compose run --rm seeder python repair_geo.py
docker exec semapa-redis redis-cli FLUSHALL
docker compose restart api-1 api-2 web nginx
```

Si quieres regenerar todo desde cero, primero truncar las tablas y luego ejecutar:

```powershell
docker compose run --rm seeder python seed.py
```

Lecturas demo:

```powershell
docker compose run --rm -e LECTURAS_PRESET=demo seeder python seed_lecturas.py
```

Carga completa:

```powershell
docker compose run --rm -e LECTURAS_PRESET=full -e LECTURAS_CONFIRMAR_FULL=SI seeder python seed_lecturas.py
```

## Validación esperada del XLSX nuevo

```text
15 distritos
54 zonas/subdistritos
100.000 infraestructuras base
120.000 medidores generados
32 gateways
9 tarifas
5 modelos de medidor
9 estados/errores IoT
```

