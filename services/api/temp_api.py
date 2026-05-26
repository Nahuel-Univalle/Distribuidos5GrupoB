from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS para el tótem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001", "http://127.0.0.1:8001", "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datos simulados de facturas
FACTURAS_MOCK = {
    100000001: {
        "periodo": "2025-05",
        "monto_bs": 313.75,
        "fecha_vencimiento": "2025-05-16",
        "estado": "PENDIENTE",
        "consumo_m3": 12.5
    },
    100000002: {
        "periodo": "2025-05",
        "monto_bs": 1141.85,
        "fecha_vencimiento": "2025-05-16",
        "estado": "VENCIDA",
        "consumo_m3": 45.5
    },
    100000003: {
        "periodo": "2025-05",
        "monto_bs": 175.50,
        "fecha_vencimiento": "2025-05-16",
        "estado": "PENDIENTE",
        "consumo_m3": 7.0
    },
    100000004: {
        "periodo": "2025-05",
        "monto_bs": 1713.94,
        "fecha_vencimiento": "2025-05-16",
        "estado": "PENDIENTE",
        "consumo_m3": 68.3
    },
    100000005: {
        "periodo": "2025-05",
        "monto_bs": 719.00,
        "fecha_vencimiento": "2025-05-16",
        "estado": "PENDIENTE",
        "consumo_m3": 28.7
    }
}

@app.get("/health")
def health():
    return {"status": "ok", "service": "semapa-api-mock"}

@app.get("/api/v1/facturas/{contrato}/ultima")
async def ultima_factura(contrato: int):
    if contrato in FACTURAS_MOCK:
        factura = FACTURAS_MOCK[contrato]
        return {
            "numero_contrato": contrato,
            "periodo": factura["periodo"],
            "monto_bs": factura["monto_bs"],
            "fecha_vencimiento": factura["fecha_vencimiento"],
            "estado": factura["estado"],
            "consumo_m3": factura["consumo_m3"]
        }
    return {"error": "Contrato no encontrado"}, 404
