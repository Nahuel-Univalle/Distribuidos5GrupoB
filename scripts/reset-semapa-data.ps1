# Limpia datos SEMAPA para rehacer el seed completo.
# Ejecutar desde la raíz del proyecto.

docker exec semapa-cassandra-1 cqlsh -e "USE semapa; TRUNCATE lecturas_raw; TRUNCATE lecturas_por_medidor; TRUNCATE lecturas_por_zona_dia; TRUNCATE cobertura_gateway; TRUNCATE facturas; TRUNCATE facturas_por_periodo; TRUNCATE medidores; TRUNCATE infraestructuras; TRUNCATE personas; TRUNCATE usuarios_sistema; TRUNCATE distritos; TRUNCATE zonas; TRUNCATE gateways; TRUNCATE modelos_medidor; TRUNCATE tarifas; TRUNCATE errores_iot; TRUNCATE tipos_infraestructura; TRUNCATE sub_alcaldias;"
docker exec semapa-redis redis-cli FLUSHALL
