#!/usr/bin/env python3
"""
Script para insertar datos de prueba de facturas en Cassandra.
Úsalo después de que Cassandra esté corriendo y las tablas creadas.

Uso:
  python infra/cassandra/init/seed_facturas.py
"""
import os
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from cassandra.cluster import Cluster


def main():
    # Conectar a Cassandra
    hosts = os.getenv("CASSANDRA_HOSTS", "localhost").split(",")
    cluster = Cluster(contact_points=hosts, port=9042)
    session = cluster.connect("semapa")

    print("Insertando facturas de prueba...")

    # Datos de prueba: (numero_contrato, periodo, consumo_m3, monto_usd, monto_bs, categoria, estado)
    test_data = [
        (100000001, "2025-05", Decimal("12.5"), Decimal("45.50"), Decimal("313.75"), "R3", "PENDIENTE"),
        (100000001, "2025-04", Decimal("11.8"), Decimal("43.20"), Decimal("297.65"), "R3", "PAGADA"),
        (100000002, "2025-05", Decimal("45.3"), Decimal("165.80"), Decimal("1141.85"), "C1", "VENCIDA"),
        (100000002, "2025-04", Decimal("42.1"), Decimal("154.30"), Decimal("1061.97"), "C1", "PAGADA"),
        (100000003, "2025-05", Decimal("8.2"), Decimal("25.50"), Decimal("175.50"), "R3", "PENDIENTE"),
        (100000003, "2025-04", Decimal("9.5"), Decimal("28.75"), Decimal("197.86"), "R3", "PAGADA"),
        (100000004, "2025-05", Decimal("67.8"), Decimal("248.90"), Decimal("1713.94"), "I", "PENDIENTE"),
        (100000004, "2025-04", Decimal("72.3"), Decimal("264.80"), Decimal("1821.41"), "I", "PAGADA"),
        (100000005, "2025-05", Decimal("28.5"), Decimal("104.50"), Decimal("719.00"), "C2", "PENDIENTE"),
        (100000005, "2025-04", Decimal("25.0"), Decimal("91.50"), Decimal("630.00"), "C2", "PAGADA"),
    ]

    insert_query = """
        INSERT INTO facturas (
            numero_contrato, periodo, factura_id, medidor_id, persona_id,
            consumo_m3, monto_usd, monto_bs, tipo_cambio, categoria_tarifa,
            desglose, fecha_emision, estado
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    try:
        for numero_contrato, periodo, consumo, monto_usd, monto_bs, categoria, estado in test_data:
            session.execute(
                insert_query,
                (
                    numero_contrato,
                    periodo,
                    uuid4(),  # factura_id
                    None,  # medidor_id
                    None,  # persona_id
                    consumo,
                    monto_usd,
                    monto_bs,
                    Decimal("6.89"),  # tipo_cambio
                    categoria,
                    None,  # desglose
                    datetime.utcnow(),
                    estado,
                ),
            )
            print(f"✓ Insertada factura: Contrato {numero_contrato}, Período {periodo}, Estado {estado}")

        print("\n✅ Todas las facturas de prueba han sido insertadas exitosamente!")

    except Exception as e:
        print(f"❌ Error al insertar facturas: {e}")
        return 1
    finally:
        session.shutdown()
        cluster.shutdown()

    return 0


if __name__ == "__main__":
    exit(main())
