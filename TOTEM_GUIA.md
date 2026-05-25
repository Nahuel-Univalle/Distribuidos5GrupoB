# 🌊 Tótem SEMAPA - Guía Completa de Implementación

## PASO 0: VERIFICAR REQUISITOS

Asegúrate de tener:
- Docker corriendo: `docker ps`
- API en `http://localhost:8000`
- Cassandra disponible
- Python 3.8+

---

## PASO 1: ACTUALIZAR EL CÓDIGO DE LA API

### ✅ Cambios realizados:

1. **Nuevo endpoint público** en `services/api/app/routers/facturas.py`:
   - Agregué: `GET /api/v1/facturas/{contrato}/ultima`
   - Retorna la última factura sin requerir autenticación
   - LISTO ✓

2. **CORS actualizado** en `services/api/app/core/config.py`:
   - Agregué: `http://localhost:8001` a `API_CORS_ORIGINS`
   - LISTO ✓

### 🚀 Redeploy de la API:

```bash
# Dentro del contenedor o en tu máquina local
cd services/api

# Opción A: Reload rápido (si está en dev mode)
# Simplemente guarda los archivos - FastAPI recarga automáticamente

# Opción B: Reiniciar el contenedor
docker restart <nombre-contenedor-api>

# Verificar que está corriendo:
curl http://localhost:8000/health
# Debería responder con 200 OK
```

---

## PASO 2: CREAR DATOS DE PRUEBA EN CASSANDRA

### Opción A: Usando el script CQL (recomendado)

```bash
# Conectarte a Cassandra
docker exec -it <nombre-contenedor-cassandra> cqlsh

# Copiar y pegar el contenido de: infra/cassandra/init/04_seed_facturas.cql
# O ejecutar directamente:
docker exec <nombre-contenedor-cassandra> cqlsh \
  -f /scripts/04_seed_facturas.cql

# Verificar que las facturas se insertaron:
docker exec -it <nombre-contenedor-cassandra> cqlsh
USE semapa;
SELECT numero_contrato, periodo, monto_bs, estado FROM facturas;
# Debería mostrar 10 filas de prueba
```

### Opción B: Usando el script Python

```bash
cd infra/cassandra/init

# Instalar driver de Cassandra si no lo tienes:
pip install cassandra-driver

# Ejecutar el script:
python seed_facturas.py

# Output esperado:
# ✓ Insertada factura: Contrato 100000001, Período 2025-05, Estado PENDIENTE
# ✓ Insertada factura: Contrato 100000001, Período 2025-04, Estado PAGADA
# ... (10 facturas)
# ✅ Todas las facturas de prueba han sido insertadas exitosamente!
```

### Contratos de prueba disponibles:
- **100000001** → Últimas 2 facturas (PENDIENTE, PAGADA)
- **100000002** → Últimas 2 facturas (VENCIDA, PAGADA)
- **100000003** → Últimas 2 facturas (PENDIENTE, PAGADA)
- **100000004** → Últimas 2 facturas (PENDIENTE, PAGADA)
- **100000005** → Últimas 2 facturas (PENDIENTE, PAGADA)

---

## PASO 3: SERVIR EL TÓTEM EN PUERTO 8001

### Opción A: Python HTTP Server (Recomendado para desarrollo)

```bash
cd c:\Users\ASUS\Desktop\UNIVERSIDAD\7moSEM\DISTRI\Practca5\Distribuidos5GrupoB

# Servir en puerto 8001
python -m http.server 8001

# Output esperado:
# Serving HTTP on 0.0.0.0 port 8001 (http://0.0.0.0:8001/) ...
```

### Opción B: Node.js http-server

```bash
npm install -g http-server

cd c:\Users\ASUS\Desktop\UNIVERSIDAD\7moSEM\DISTRI\Practca5\Distribuidos5GrupoB

http-server -p 8001

# Output esperado:
# Hit CTRL-C to stop the server
# http://127.0.0.1:8001
```

### Opción C: Docker (si quieres containerizar)

```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 8001
```

```bash
docker build -t semapa-totem .
docker run -p 8001:80 semapa-totem
```

---

## PASO 4: PRUEBA EL TÓTEM

### Abrir en navegador:

```
http://localhost:8001/totem.html
```

### Pantalla esperada:
- **Encabezado**: "🌊 SEMAPA"
- **Subtítulo**: "Consulta tu deuda de agua..."
- **Campo grande**: Display vacío (para mostrar números)
- **Teclado**: 10 botones (1-9, 0), Borrar, Limpiar, Consultar
- **Estilos**: Fondo blanco/crema, texto oscuro, botones grandes (80px)

### Test 1: Contrato válido

1. Haz clic en: **1** → **0** → **0** → **0** → **0** → **0** → **0** → **0** → **1**
2. Debería mostrar: `100000001` en el display
3. Haz clic en **CONSULTAR**
4. Espera 1-2 segundos
5. Debería aparecer:
   - ✅ **Contrato**: 100000001
   - ✅ **Periodo**: 2025-05
   - ✅ **Deuda (Bs)**: 313.75
   - ✅ **Vencimiento**: 16/05/2025 (aproximadamente)
   - ✅ **Consumo**: 12.5 m³
   - ✅ **Estado**: PENDIENTE (badge amarillo)

### Test 2: Contrato inexistente

1. Ingresa: **9** → **9** → **9** → **9** → **9** → **9** → **9** → **9** → **9** → **9**
2. Haz clic en **CONSULTAR**
3. Debería mostrar: ❌ "Número de contrato '9999999999' no encontrado..."

### Test 3: Error de conexión (simular desconexión)

1. Detén el contenedor de la API: `docker stop <api-container>`
2. Intenta consultar
3. Debería mostrar: ❌ "No se pudo conectar con el servidor..."
4. Reinicia el contenedor: `docker start <api-container>`

### Test 4: Botones

- **BORRAR**: Elimina el último número (usa backspace o clic en botón)
- **LIMPIAR**: Borra todo y vuelve a la pantalla inicial
- **NUEVA CONSULTA**: Igual que LIMPIAR (después de ver resultados)
- **IMPRIMIR**: Abre el diálogo de impresión (Ctrl+P o clic en botón)

### Test 5: Soporte de teclado físico

Prueba sin hacer clic en botones:
- Escribe números: `100000001`
- Presiona **Enter** para consultar
- Usa **Backspace** para borrar
- Usa **Escape** para limpiar todo

---

## PASO 5: VALIDAR CORS

Si ves error de CORS en la consola del navegador:

```
Access to fetch at 'http://localhost:8000/api/v1/facturas/100000001/ultima' 
from origin 'http://localhost:8001' has been blocked by CORS policy
```

### Solución:

1. Verifica que `config.py` tiene: `API_CORS_ORIGINS: str = "http://localhost,http://localhost:5173,http://localhost:8001"`
2. Reinicia el contenedor de la API
3. Limpia cache del navegador (Ctrl+Shift+Delete)
4. Intenta de nuevo

---

## PASO 6: PROBAR CON OTROS CONTRATOS

Usa estos números para probar diferentes estados:

```
100000001 → PENDIENTE (Deuda: 313.75 Bs)
100000002 → VENCIDA  (Deuda: 1141.85 Bs) ⚠️
100000003 → PENDIENTE (Deuda: 175.50 Bs)
100000004 → PENDIENTE (Deuda: 1713.94 Bs) [Comercial]
100000005 → PENDIENTE (Deuda: 719.00 Bs)
```

---

## PASO 7: DESPLEGAR EN PRODUCCIÓN

### En servidor real:

```bash
# 1. Copiar totem.html al servidor web
scp totem.html usuario@servidor:/var/www/semapa/

# 2. Configurar Nginx o Apache para servir en puerto 8001
# En /etc/nginx/sites-available/totem:
server {
    listen 8001;
    server_name localhost;
    
    location / {
        root /var/www/semapa;
        try_files $uri /totem.html;
    }
}

# 3. Habilitar
sudo ln -s /etc/nginx/sites-available/totem /etc/nginx/sites-enabled/
sudo systemctl reload nginx

# 4. Verificar
curl http://localhost:8001/totem.html
```

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### El tótem se ve roto (letras pequeñas, botones minúsculos)

```
→ Verifica que estés usando un navegador moderno (Chrome, Firefox, Edge, Safari)
→ Presiona F11 para pantalla completa
→ Aumenta el zoom (Ctrl++)
```

### "Contrato no encontrado" cuando ingreso un número válido

```
→ Verifica que las facturas se insertaron: SELECT * FROM semapa.facturas LIMIT 5;
→ Verifica que usas un número que existe: 100000001, 100000002, etc.
→ Comprueba que la API está corriendo: curl http://localhost:8000/health
```

### CORS error en consola

```
→ Abre DevTools (F12) → Consola
→ Verifica si hay error: "has been blocked by CORS policy"
→ Solución: Reinicia API después de cambiar config.py
```

### La API no recarga cambios

```
→ Si usas docker: docker restart <nombre-contenedor>
→ Si usas FastAPI en desarrollo: debería recargar automáticamente
→ Verifica que no hay puerto 8000 siendo usado por otra aplicación
```

### El teclado no funciona

```
→ Intenta con mouse (haz clic en los botones)
→ Si usas teclado físico: deberían funcionar números normales + Enter/Backspace/Escape
→ Verifica que el navegador tiene el foco (haz clic en el campo display primero)
```

---

## 📊 RESUMEN DE CAMBIOS

| Archivo | Cambio |
|---------|--------|
| `services/api/app/routers/facturas.py` | ✅ Agregado endpoint `GET /{contrato}/ultima` |
| `services/api/app/core/config.py` | ✅ CORS: agregado `http://localhost:8001` |
| `totem.html` | ✅ Completamente mejorado (números, interfaz accesible) |
| `infra/cassandra/init/04_seed_facturas.cql` | ✅ Script CQL para datos de prueba |
| `infra/cassandra/init/seed_facturas.py` | ✅ Script Python para datos de prueba |

---

## ✅ CHECKLIST FINAL

- [ ] API redeployed con nuevo endpoint
- [ ] CORS configurado para puerto 8001
- [ ] Datos de prueba insertados en Cassandra (10 facturas)
- [ ] Tótem sirviendo en http://localhost:8001
- [ ] Test 1: Contrato válido → Muestra deuda ✓
- [ ] Test 2: Contrato inválido → Mensaje de error ✓
- [ ] Test 3: Botones → Funcionan correctamente ✓
- [ ] Test 4: Imprimir → Abre diálogo de impresión ✓
- [ ] Test 5: Teclado físico → Funciona (números, Enter, Backspace) ✓
- [ ] Diseño accesible → Letras grandes, botones grandes, alto contraste ✓

---

## 📞 SOPORTE

Si algo no funciona:

1. Revisa los logs:
   ```bash
   docker logs <api-container>
   docker logs <cassandra-container>
   ```

2. Verifica conectividad:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8001/totem.html
   ```

3. Abre la consola del navegador (F12) y revisa errores

¡Éxito! 🚀
