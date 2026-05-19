#!/bin/bash

# SEMAPA API - Ejemplos cURL de las 25 Consultas
# Proyecto: Smart Water Cochabamba
# Autor: Persona 4 - Backend Engineer

# ==============================================================================
# CONFIGURACIÓN
# ==============================================================================

API_BASE="http://localhost:8000/api/v1"

# Obtener token primero (guardar en $TOKEN después del login)
# TOKEN=$(curl -s -X POST "$API_BASE/auth/login" \
#   -H "Content-Type: application/json" \
#   -d '{"username":"admin","password":"12345"}' | jq -r '.access_token')

# Para los ejemplos, usar TOKEN variable
TOKEN="your_jwt_token_here"

# ==============================================================================
# AUTENTICACIÓN
# ==============================================================================

echo "==============================================================="
echo "1. LOGIN Y OBTENER TOKEN"
echo "==============================================================="

curl -X POST "$API_BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "12345"
  }' | jq '.'

# Guardar token como: export TOKEN="<value_del_access_token>"

echo ""
echo "==============================================================="
echo "2. OBTENER USUARIO ACTUAL"
echo "==============================================================="

curl -X GET "$API_BASE/auth/me" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# ==============================================================================
# CONSULTAS (25)
# ==============================================================================

echo ""
echo "==============================================================="
echo "CONSULTA 1: Consumo Promedio por Distrito (8h)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/1?horas=8" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 2: Comparativa Consumo 4 Semanas"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/2?distritos=1,2,3" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:5]'

echo ""
echo "==============================================================="
echo "CONSULTA 3: Consumos Excesivos (>45 m³)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/3?umbral_m3=45.0" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 4: Medidores Activos por Distrito y Zona"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/4" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:5]'

echo ""
echo "==============================================================="
echo "CONSULTA 5: Medidores Fuera de Servicio"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/5" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:5]'

echo ""
echo "==============================================================="
echo "CONSULTA 6: Modelos con Mayor Tasa de Fallos"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/6" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 7: Consumo Promedio Mensual por Tarifa y Distrito"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/7" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:5]'

echo ""
echo "==============================================================="
echo "CONSULTA 8: Zonas con Consumo Anómalo"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/8" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 9: Lecturas Fallidas Último Mes"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/9" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 10: Porcentaje de Medidores >4 Años"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/10?anios=4" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 11: Per Cápita Residencial"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/11" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:5]'

echo ""
echo "==============================================================="
echo "CONSULTA 12: Top 3 Consumidores por Distrito"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/12" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 13: Zonas que Requieren Renovación"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/13" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 14: Zonas con Errores por Distrito (MOLLE)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/14?distrito=2" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 15: Cobertura de Antenas"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/15" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:5]'

echo ""
echo "==============================================================="
echo "CONSULTA 16: Proyección de Demanda 5 Años (2.6% anual)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/16?crecimiento_anual_pct=2.6" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 17: Impacto Cambio Tarifa (P → R4)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/17?desde_tarifa=P&hacia_tarifa=R4" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 18: Medidores Sin Reporte (7 días)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/18?dias=7" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 19: Proyección de Ingresos Mes"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/19" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 20: Consumo Mínimo Residencial (12 m³)"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/20?consumo_minimo_m3=12.0" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 21: Ingresos en Pies Cúbicos"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/21" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 22: Detección de Anomalías"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/22" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "CONSULTA 23: Análisis Cobertura Gateways"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/23" \
  -H "Authorization: Bearer $TOKEN" | jq '.[:3]'

echo ""
echo "==============================================================="
echo "CONSULTA 25: Análisis Predictivo Estratégico"
echo "==============================================================="

curl -X GET "$API_BASE/consultas/25" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# ==============================================================================
# ENDPOINTS CRÍTICOS
# ==============================================================================

echo ""
echo "==============================================================="
echo "KPIs - Dashboard"
echo "==============================================================="

curl -X GET "$API_BASE/dashboard/kpis" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "BÚSQUEDA - Por Contrato"
echo "==============================================================="

curl -X GET "$API_BASE/buscar?q=123456" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "BÚSQUEDA - Por MAC"
echo "==============================================================="

curl -X GET "$API_BASE/buscar?q=AB:CD:12:34:56:78" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "BÚSQUEDA - Por Número de Serie"
echo "==============================================================="

curl -X GET "$API_BASE/buscar?q=SN=254-41269-1411" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "==============================================================="
echo "LECTURA MANUAL - Registrar desde Móvil"
echo "==============================================================="

curl -X POST "$API_BASE/lecturas/manual" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "numero_contrato": 123456,
    "lectura_litros": 456789,
    "lat": -17.394,
    "lon": -66.157,
    "foto_url": "s3://bucket/foto_2025_05_19_145523.jpg"
  }' | jq '.'

# ==============================================================================
# NOTAS DE PERFORMANCE
# ==============================================================================

echo ""
echo "==============================================================="
echo "NOTAS DE PERFORMANCE"
echo "==============================================================="
echo ""
echo "- Agregar -w '\\nTiempo total: %{time_total}s\\n' a cualquier curl para ver el tiempo de respuesta"
echo "- Ejemplo:"
echo ""
echo "curl -X GET '$API_BASE/consultas/19' \\"
echo "  -H 'Authorization: Bearer \$TOKEN' \\"
echo "  -w '\\nTiempo: %{time_total}s\\n' | jq '.'"
echo ""
echo "- Objetivo: <2s para todas las consultas (con cache)"
echo "- Sin cache: pueden ser más lentas en primer acceso"
echo ""
