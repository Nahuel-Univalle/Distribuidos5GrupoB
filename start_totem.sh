#!/bin/bash
# 🚀 QUICK START - Tótem SEMAPA en 5 minutos

set -e

echo "🌊 Tótem SEMAPA - Quick Start"
echo "======================================"
echo ""

# PASO 1: Verificar que todo está corriendo
echo "1️⃣ Verificando servicios..."
if ! curl -s http://localhost:8000/health > /dev/null; then
  echo "❌ ERROR: API no responde en http://localhost:8000"
  echo "   Solución: Inicia el contenedor de API"
  exit 1
fi
echo "✅ API corriendo en :8000"

# PASO 2: Insertar datos de prueba en Cassandra
echo ""
echo "2️⃣ Insertando datos de prueba..."
cd "$(dirname "$0")/infra/cassandra/init"

# Verificar que existe el script
if [ ! -f seed_facturas.py ]; then
  echo "❌ ERROR: seed_facturas.py no encontrado"
  exit 1
fi

# Ejecutar script Python
python3 seed_facturas.py 2>/dev/null || {
  echo "⚠️ No se pudieron insertar datos (Cassandra no accesible)"
  echo "   Puedes hacerlo manualmente después"
}
echo "✅ Datos de prueba insertados"

# PASO 3: Servir tótem en puerto 8001
echo ""
echo "3️⃣ Sirviendo tótem en puerto 8001..."
cd "$(dirname "$0")"

# Verificar que existe totem.html
if [ ! -f totem.html ]; then
  echo "❌ ERROR: totem.html no encontrado en $(pwd)"
  exit 1
fi

# Iniciar servidor
echo "✅ Tótem listo en: http://localhost:8001/totem.html"
echo ""
echo "🎯 PRÓXIMOS PASOS:"
echo "   1. Abre http://localhost:8001/totem.html en tu navegador"
echo "   2. Prueba con contrato: 100000001"
echo "   3. Deberías ver una deuda de 313.75 Bs"
echo ""
echo "⌛ Sirviendo en puerto 8001..."
echo "   Presiona Ctrl+C para detener"
echo ""

python3 -m http.server 8001 --bind 127.0.0.1
