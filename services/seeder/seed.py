"""
insertar_usuarios.py — Solo inserta los 3 usuarios del sistema.
Los datos ya están cargados de antes.
"""

from cassandra.cluster import Cluster
from datetime import datetime
import hashlib

cluster = Cluster(['127.0.0.1'], port=9042, protocol_version=4)
session = cluster.connect('semapa')
print("✅ Conectado")

users = [
    ('alcaldia', 'Alcaldia2025!', 'ALCALDIA', 'Alcaldía Cochabamba', 'alcaldia@semapa.bo'),
    ('gerencia', 'Gerencia2025!', 'GERENCIA', 'Gerencia SEMAPA', 'gerencia@semapa.bo'),
    ('contabilidad', 'Contab2025!', 'CONTABILIDAD', 'Contabilidad SEMAPA', 'contabilidad@semapa.bo'),
]

# Limpiar usuarios viejos
try:
    session.execute("TRUNCATE usuarios_sistema")
except:
    pass

# Insertar nuevos
ps = session.prepare("INSERT INTO usuarios_sistema (username, password_hash, rol, nombre, email, activo, fecha_creacion) VALUES (?, ?, ?, ?, ?, ?, ?)")

for username, password, rol, nombre, email in users:
    h = hashlib.sha256(password.encode()).hexdigest()
    session.execute(ps, (username, h, rol, nombre, email, True, datetime.utcnow()))
    print(f"✅ {username} insertado")

# Verificar
print("\n📊 Usuarios en BD:")
for row in session.execute("SELECT username, rol, email FROM usuarios_sistema"):
    print(f"   {row.username} | {row.rol} | {row.email}")

session.shutdown()
cluster.shutdown()
print("\n🎉 ¡Usuarios listos! Ya puedes hacer login.")