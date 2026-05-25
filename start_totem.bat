@echo off
REM 🚀 QUICK START - Tótem SEMAPA en 5 minutos (Windows)

setlocal enabledelayedexpansion

echo.
echo 🌊 Tótem SEMAPA - Quick Start (Windows)
echo ======================================
echo.

REM PASO 1: Verificar que todo está corriendo
echo 1️⃣ Verificando servicios...

curl -s http://localhost:8000/health >nul 2>&1
if !errorlevel! neq 0 (
  echo ❌ ERROR: API no responde en http://localhost:8000
  echo    Solución: Inicia el contenedor de API
  pause
  exit /b 1
)
echo ✅ API corriendo en :8000

REM PASO 2: Insertar datos de prueba en Cassandra
echo.
echo 2️⃣ Insertando datos de prueba...

cd /d "%~dp0infra\cassandra\init"

if not exist seed_facturas.py (
  echo ❌ ERROR: seed_facturas.py no encontrado
  pause
  exit /b 1
)

python seed_facturas.py >nul 2>&1
if !errorlevel! neq 0 (
  echo ⚠️ No se pudieron insertar datos (Cassandra no accesible)
  echo    Puedes hacerlo manualmente después
) else (
  echo ✅ Datos de prueba insertados
)

REM PASO 3: Servir tótem en puerto 8001
echo.
echo 3️⃣ Sirviendo tótem en puerto 8001...

cd /d "%~dp0"

if not exist totem.html (
  echo ❌ ERROR: totem.html no encontrado en %cd%
  pause
  exit /b 1
)

echo ✅ Tótem listo en: http://localhost:8001/totem.html
echo.
echo 🎯 PRÓXIMOS PASOS:
echo    1. Abre http://localhost:8001/totem.html en tu navegador
echo    2. Prueba con contrato: 100000001
echo    3. Deberías ver una deuda de 313.75 Bs
echo.
echo ⌛ Sirviendo en puerto 8001...
echo    Presiona Ctrl+C para detener
echo.

python -m http.server 8001

pause
