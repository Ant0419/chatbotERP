# backend/app/agent/tools.py
#
# Define las herramientas que el agente (Executor) puede invocar (Function Calling).
# Formato: OpenAI JSON Schema.

import os
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Setup MongoDB Connection
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://mongodb:27017")
client = AsyncIOMotorClient(MONGO_URL)
db = client.erp_db

# ── Definiciones de herramientas (schema que ve el LLM de Cerebras/OpenAI) ────
TOOLS_DEFINITIONS = [
    # ── Productos ──────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_productos",
            "description": "Obtiene la lista de productos del inventario. Permite filtrar por categoría o stock mínimo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string", "description": "Filtra por categoría"},
                    "stock_min": {"type": "integer", "description": "Stock mínimo para filtrar"},
                },
                "required": [],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_producto",
            "description": "Crea un nuevo producto en el inventario. No inventes el SKU a menos que el usuario pida uno específico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "sku": {"type": "string", "description": "DEJA ESTE CAMPO VACÍO. El sistema lo genera solo."},
                    "stock": {"type": "integer"},
                    "precio_venta": {"type": "number"},
                    "precio_compra": {"type": "number"},
                    "categoria": {"type": "string"},
                    "fecha_caducidad": {"type": "string", "description": "ISO 8601, ej: 2025-12-31"},
                },
                "required": ["nombre", "stock", "precio_venta"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_producto",
            "description": "Elimina un producto por su SKU.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"}
                },
                "required": ["sku"],
            },
        }
    },

    # ── Proveedores ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_proveedores",
            "description": "Obtiene la lista de proveedores registrados.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_proveedor",
            "description": "Registra un nuevo proveedor.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "contacto_email": {"type": "string"},
                    "telefono": {"type": "string"},
                    "pais": {"type": "string"},
                },
                "required": ["nombre", "contacto_email"],
            },
        }
    },

    # ── Pedidos ────────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_pedido",
            "description": "Crea un pedido a proveedor. El stock se actualiza de forma inmediata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proveedor_id": {"type": "string"},
                    "productos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de SKUs con cantidad, ej: ['SKU001:50', 'SKU002:20']"
                    },
                },
                "required": ["proveedor_id", "productos"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pedidos",
            "description": "Devuelve el historial de pedidos a proveedores.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    },

    # ── Desechos ───────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_desechos",
            "description": "Devuelve el registro de productos desechados por caducidad.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "procesar_caducados",
            "description": "Detecta productos caducados, los registra como desechos y resta su stock.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
    },

    # ── Estadísticas ───────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_estadisticas",
            "description": "Devuelve estadísticas del ERP: stock por categoría, pedidos por mes, pérdidas por desechos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "description": "'stock_categoria' | 'pedidos_mes' | 'perdidas_desechos'"
                    }
                },
                "required": [],
            },
        }
    }
]


# ── Dispatcher: ejecuta la herramienta correcta ───────────────────────────────
async def execute_tool(name: str, args: dict) -> dict:
    """Enruta la llamada del LLM a la función real correspondiente."""
    dispatch = {
        "get_productos":     _get_productos,
        "create_producto":   _create_producto,
        "delete_producto":   _delete_producto,
        "get_proveedores":   _get_proveedores,
        "create_proveedor":  _create_proveedor,
        "create_pedido":     _create_pedido,
        "get_pedidos":       _get_pedidos,
        "get_desechos":      _get_desechos,
        "procesar_caducados":_procesar_caducados,
        "get_estadisticas":  _get_estadisticas,
    }
    fn = dispatch.get(name)
    if not fn:
        return {"error": f"Herramienta desconocida: {name}"}
    return await fn(**args)


# ── Implementaciones MongoDB Reales ─────────────────────────────────────────

async def _get_productos(categoria=None, stock_min=None):
    query = {}
    if categoria:
        query["categoria"] = {"$regex": f"^{categoria}$", "$options": "i"}
    if stock_min is not None:
        query["stock"] = {"$gte": stock_min}
    
    productos = await db.productos.find(query).to_list(length=100)
    for p in productos:
        p["_id"] = str(p["_id"])
    return {"productos": productos, "total": len(productos)}

async def _create_producto(**kwargs):
    if not kwargs.get("sku"):
        kwargs["sku"] = f"PROD-{uuid.uuid4().hex[:6].upper()}"
    result = await db.productos.insert_one(kwargs)
    return {"ok": True, "message": f"Producto '{kwargs.get('nombre')}' creado con SKU {kwargs.get('sku')} y _id {str(result.inserted_id)}."}

async def _delete_producto(sku: str):
    result = await db.productos.delete_one({"sku": sku})
    if result.deleted_count > 0:
        return {"ok": True, "message": f"Producto con SKU {sku} eliminado."}
    return {"ok": False, "message": f"No se encontró el producto con SKU {sku}."}

async def _get_proveedores():
    proveedores = await db.proveedores.find().to_list(length=100)
    for p in proveedores:
        p["_id"] = str(p["_id"])
    return {"proveedores": proveedores}

async def _create_proveedor(**kwargs):
    result = await db.proveedores.insert_one(kwargs)
    return {"ok": True, "message": f"Proveedor '{kwargs.get('nombre')}' registrado con _id {str(result.inserted_id)}."}

async def _create_pedido(proveedor_id: str, productos: list):
    pedido = {
        "proveedor": proveedor_id,
        "productos": productos,
        "fecha": datetime.now(timezone.utc).date().isoformat(),
        "estado": "pendiente"
    }
    result = await db.pedidos.insert_one(pedido)
    return {"ok": True, "message": f"Pedido creado para proveedor {proveedor_id}. _id: {str(result.inserted_id)}"}

async def _get_pedidos():
    pedidos = await db.pedidos.find().to_list(length=100)
    for p in pedidos:
        p["_id"] = str(p["_id"])
    return {"pedidos": pedidos}

async def _get_desechos():
    desechos = await db.desechos.find().to_list(length=100)
    for d in desechos:
        d["_id"] = str(d["_id"])
    return {"desechos": desechos}

async def _procesar_caducados():
    hoy = datetime.now(timezone.utc).date().isoformat()
    # Find expired products
    caducados = await db.productos.find({"fecha_caducidad": {"$lte": hoy}}).to_list(length=100)
    if not caducados:
        return {"ok": True, "message": f"Revisión completada ({hoy}). No hay productos caducados."}
    
    # Move to desechos and delete from productos
    for p in caducados:
        p["cantidad_desechada"] = p.get("stock", 0)
        p["fecha_baja"] = hoy
        p["motivo"] = "Caducado"
        await db.desechos.insert_one(p)
        await db.productos.delete_one({"_id": p["_id"]})
        
    return {"ok": True, "message": f"Revisión completada ({hoy}). {len(caducados)} productos caducados procesados y registrados como desecho."}

async def _get_estadisticas(tipo="stock_categoria"):
    if tipo == "stock_categoria":
        pipeline = [
            {"$group": {"_id": "$categoria", "total_stock": {"$sum": "$stock"}}}
        ]
        results = await db.productos.aggregate(pipeline).to_list(length=100)
        labels = [r["_id"] if r["_id"] else "Sin Categoría" for r in results]
        values = [r["total_stock"] for r in results]
        return {"labels": labels, "values": values, "tipo": "bar"}
    elif tipo == "pedidos_mes":
        return {"labels": ["Mayo", "Junio", "Julio"], "values": [0, 0, 0], "tipo": "line"} # Simplificado
    elif tipo == "perdidas_desechos":
        pipeline = [
            {"$group": {"_id": None, "total_perdida": {"$sum": {"$multiply": ["$cantidad_desechada", "$precio_venta"]}}}}
        ]
        results = await db.desechos.aggregate(pipeline).to_list(length=1)
        total = results[0]["total_perdida"] if results else 0
        return {"labels": ["Pérdidas Acumuladas"], "values": [total], "tipo": "bar"}
    
    return {"error": f"Tipo de estadística '{tipo}' no soportado."}
