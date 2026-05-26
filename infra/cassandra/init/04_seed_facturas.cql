-- Script para insertar facturas de prueba en SEMAPA
-- Ejecutar con: cqlsh -f seed_facturas.cql

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000001, '2025-05', uuid(), NULL, NULL, 12.5, 45.50, 313.75, 6.89, 'R3', null, '2025-05-01T10:00:00Z', 'PENDIENTE');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000001, '2025-04', uuid(), NULL, NULL, 11.8, 43.20, 297.65, 6.89, 'R3', null, '2025-04-01T10:00:00Z', 'PAGADA');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000002, '2025-05', uuid(), NULL, NULL, 45.3, 165.80, 1141.85, 6.89, 'C1', null, '2025-05-01T10:00:00Z', 'VENCIDA');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000002, '2025-04', uuid(), NULL, NULL, 42.1, 154.30, 1061.97, 6.89, 'C1', null, '2025-04-01T10:00:00Z', 'PAGADA');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000003, '2025-05', uuid(), NULL, NULL, 8.2, 25.50, 175.50, 6.89, 'R3', null, '2025-05-01T10:00:00Z', 'PENDIENTE');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000003, '2025-04', uuid(), NULL, NULL, 9.5, 28.75, 197.86, 6.89, 'R3', null, '2025-04-01T10:00:00Z', 'PAGADA');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000004, '2025-05', uuid(), NULL, NULL, 67.8, 248.90, 1713.94, 6.89, 'I', null, '2025-05-01T10:00:00Z', 'PENDIENTE');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000004, '2025-04', uuid(), NULL, NULL, 72.3, 264.80, 1821.41, 6.89, 'I', null, '2025-04-01T10:00:00Z', 'PAGADA');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000005, '2025-05', uuid(), NULL, NULL, 28.5, 104.50, 719.00, 6.89, 'C2', null, '2025-05-01T10:00:00Z', 'PENDIENTE');

INSERT INTO semapa.facturas (numero_contrato, periodo, factura_id, medidor_id, persona_id, consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa, desglose, fecha_emision, estado)
VALUES (100000005, '2025-04', uuid(), NULL, NULL, 25.0, 91.50, 630.00, 6.89, 'C2', null, '2025-04-01T10:00:00Z', 'PAGADA');
