# backend/app/agent/tools.py
#
# Define las herramientas que el agente (Executor) puede invocar (Function Calling).
# Formato: OpenAI JSON Schema.

import os
import uuid
from datetime import datetime, timezone
from bson import ObjectId
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
                    "fecha_caducidad": {"type": "string", "description": "Fecha de caducidad ISO 8601, ej: 2025-12-31. MUY IMPORTANTE para control de desechos."},
                },
                "required": ["nombre", "stock", "precio_venta"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_producto",
            "description": "Actualiza un producto existente buscándolo por su SKU. Solo se modifican los campos que se proporcionen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "SKU del producto a actualizar (obligatorio para identificar)."},
                    "nombre": {"type": "string", "description": "Nuevo nombre del producto."},
                    "stock": {"type": "integer", "description": "Nuevo valor de stock."},
                    "precio_venta": {"type": "number", "description": "Nuevo precio de venta."},
                    "precio_compra": {"type": "number", "description": "Nuevo precio de compra."},
                    "categoria": {"type": "string", "description": "Nueva categoría."},
                    "fecha_caducidad": {"type": "string", "description": "Nueva fecha de caducidad ISO 8601."},
                },
                "required": ["sku"],
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
            "description": "Registra un nuevo proveedor. El sistema genera automáticamente un codigo_proveedor (PROV-XXXXXX). NO inventes el código.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string", "description": "Nombre del proveedor."},
                    "contacto_email": {"type": "string", "description": "Email de contacto."},
                    "telefono": {"type": "string", "description": "Teléfono de contacto."},
                    "pais": {"type": "string", "description": "País de origen del proveedor."},
                },
                "required": ["nombre", "contacto_email"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_proveedor",
            "description": "Actualiza los datos de un proveedor existente buscándolo por su codigo_proveedor (ej: PROV-ABC123). Solo se modifican los campos proporcionados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_proveedor": {"type": "string", "description": "Código del proveedor (ej: PROV-ABC123). Obligatorio."},
                    "nombre": {"type": "string", "description": "Nuevo nombre."},
                    "contacto_email": {"type": "string", "description": "Nuevo email."},
                    "telefono": {"type": "string", "description": "Nuevo teléfono."},
                    "pais": {"type": "string", "description": "Nuevo país."},
                },
                "required": ["codigo_proveedor"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_proveedor",
            "description": "Elimina un proveedor por su codigo_proveedor (ej: PROV-ABC123).",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_proveedor": {"type": "string", "description": "Código del proveedor a eliminar (ej: PROV-ABC123)."}
                },
                "required": ["codigo_proveedor"],
            },
        }
    },

    # ── Pedidos a Proveedor ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_pedido",
            "description": "Crea un pedido a proveedor. REQUIERE un codigo_proveedor válido (ej: PROV-ABC123). Si el proveedor no existe, devuelve error. El stock se suma INSTANTÁNEAMENTE. El sistema genera un codigo_pedido automático (ORD-XXXXXX).",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_proveedor": {"type": "string", "description": "Código del proveedor (ej: PROV-ABC123). DEBE existir previamente."},
                    "productos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de 'SKU:cantidad'. Ej: ['PROD-ABC123:50', 'PROD-DEF456:20']"
                    },
                },
                "required": ["codigo_proveedor", "productos"],
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
    {
        "type": "function",
        "function": {
            "name": "update_pedido",
            "description": "Actualiza el estado de un pedido existente buscándolo por su codigo_pedido (ej: ORD-ABC123). Se puede cambiar el estado a 'completado', 'recibido' o 'cancelado'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_pedido": {"type": "string", "description": "Código del pedido (ej: ORD-ABC123). Obligatorio."},
                    "estado": {"type": "string", "description": "Nuevo estado: 'completado', 'recibido' o 'cancelado'."}
                },
                "required": ["codigo_pedido", "estado"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_pedido",
            "description": "Elimina un pedido por su codigo_pedido (ej: ORD-ABC123). NOTA: no revierte el stock que ya se sumó.",
            "parameters": {
                "type": "object",
                "properties": {
                    "codigo_pedido": {"type": "string", "description": "Código del pedido a eliminar (ej: ORD-ABC123)."}
                },
                "required": ["codigo_pedido"],
            },
        }
    },

    # ── Desechos ───────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_desechos",
            "description": "Devuelve el registro histórico de productos desechados por caducidad.",
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
            "description": "Revisa todos los productos con fecha_caducidad vencida. Los elimina del inventario, pone su stock a 0 y los registra en la colección de desechos indicando la pérdida. Usar cuando el usuario pida revisar caducados o gestionar desechos.",
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
            "description": "Devuelve estadísticas del ERP. Tipos disponibles: 'stock_categoria' (stock agrupado por categoría), 'top_productos_stock' (top 10 productos con más stock), 'pedidos_mes' (pedidos agrupados por mes), 'perdidas_desechos' (pérdidas económicas acumuladas por desechos).",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "description": "'stock_categoria' | 'top_productos_stock' | 'pedidos_mes' | 'perdidas_desechos'"
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
        "get_productos":      _get_productos,
        "create_producto":    _create_producto,
        "update_producto":    _update_producto,
        "delete_producto":    _delete_producto,
        "get_proveedores":    _get_proveedores,
        "create_proveedor":   _create_proveedor,
        "update_proveedor":   _update_proveedor,
        "delete_proveedor":   _delete_proveedor,
        "create_pedido":      _create_pedido,
        "get_pedidos":        _get_pedidos,
        "update_pedido":      _update_pedido,
        "delete_pedido":      _delete_pedido,
        "get_desechos":       _get_desechos,
        "procesar_caducados": _procesar_caducados,
        "get_estadisticas":   _get_estadisticas,
    }
    fn = dispatch.get(name)
    if not fn:
        return {"error": f"Herramienta desconocida: {name}"}
    return await fn(**args)


# ══════════════════════════════════════════════════════════════════════════════
# Implementaciones MongoDB
# ══════════════════════════════════════════════════════════════════════════════

# ── Productos ─────────────────────────────────────────────────────────────────

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
    kwargs["fecha_creacion"] = datetime.now(timezone.utc).isoformat()
    result = await db.productos.insert_one(kwargs)
    return {"ok": True, "message": f"Producto '{kwargs.get('nombre')}' creado con SKU {kwargs.get('sku')} y _id {str(result.inserted_id)}."}

async def _update_producto(sku: str, **kwargs):
    # Filtrar campos vacíos o None; no actualizar el propio SKU
    update_fields = {k: v for k, v in kwargs.items() if v is not None and k != "sku"}
    if not update_fields:
        return {"ok": False, "message": "No se proporcionaron campos para actualizar."}
    result = await db.productos.update_one({"sku": sku}, {"$set": update_fields})
    if result.matched_count == 0:
        return {"ok": False, "message": f"No se encontró el producto con SKU {sku}."}
    return {"ok": True, "message": f"Producto con SKU {sku} actualizado correctamente. Campos modificados: {list(update_fields.keys())}"}

async def _delete_producto(sku: str):
    result = await db.productos.delete_one({"sku": sku})
    if result.deleted_count > 0:
        return {"ok": True, "message": f"Producto con SKU {sku} eliminado."}
    return {"ok": False, "message": f"No se encontró el producto con SKU {sku}."}


# ── Proveedores ───────────────────────────────────────────────────────────────

async def _get_proveedores():
    proveedores = await db.proveedores.find().to_list(length=100)
    for p in proveedores:
        p["_id"] = str(p["_id"])
    return {"proveedores": proveedores, "total": len(proveedores)}

async def _create_proveedor(**kwargs):
    kwargs["codigo_proveedor"] = f"PROV-{uuid.uuid4().hex[:6].upper()}"
    kwargs["fecha_registro"] = datetime.now(timezone.utc).isoformat()
    result = await db.proveedores.insert_one(kwargs)
    return {"ok": True, "message": f"Proveedor '{kwargs.get('nombre')}' registrado con código {kwargs['codigo_proveedor']}."}

async def _update_proveedor(codigo_proveedor: str, **kwargs):
    update_fields = {k: v for k, v in kwargs.items() if v is not None and k != "codigo_proveedor"}
    if not update_fields:
        return {"ok": False, "message": "No se proporcionaron campos para actualizar."}
    result = await db.proveedores.update_one({"codigo_proveedor": codigo_proveedor}, {"$set": update_fields})
    if result.matched_count == 0:
        return {"ok": False, "message": f"No se encontró el proveedor con código {codigo_proveedor}."}
    return {"ok": True, "message": f"Proveedor {codigo_proveedor} actualizado. Campos: {list(update_fields.keys())}"}

async def _delete_proveedor(codigo_proveedor: str):
    result = await db.proveedores.delete_one({"codigo_proveedor": codigo_proveedor})
    if result.deleted_count > 0:
        return {"ok": True, "message": f"Proveedor {codigo_proveedor} eliminado."}
    return {"ok": False, "message": f"No se encontró el proveedor con código {codigo_proveedor}."}


# ── Pedidos a Proveedor ───────────────────────────────────────────────────────

async def _create_pedido(codigo_proveedor: str, productos: list):
    """
    Crea un pedido y suma el stock INSTANTÁNEAMENTE a cada producto.
    VALIDA que el proveedor exista antes de proceder.
    productos es una lista de strings con formato 'SKU:cantidad'.
    """
    # ── Validar integridad referencial: el proveedor DEBE existir ──
    proveedor = await db.proveedores.find_one({"codigo_proveedor": codigo_proveedor})
    if not proveedor:
        return {
            "ok": False,
            "message": f"Error de integridad: El proveedor con código '{codigo_proveedor}' no existe. Infórmale al usuario que debe crear el proveedor primero."
        }

    detalles = []
    errores = []

    for item in productos:
        if not isinstance(item, str):
            errores.append(f"Formato inválido (no es texto): '{item}'")
            continue
        try:
            parts = item.split(":")
            sku = parts[0].strip() if parts[0] else ""
            cantidad = int(parts[1].strip() if len(parts) > 1 and parts[1] else 0)
        except (IndexError, ValueError):
            errores.append(f"Formato inválido: '{item}'. Usa 'SKU:cantidad'.")
            continue

        # Buscar el producto y sumar stock
        producto = await db.productos.find_one({"sku": sku})
        if not producto:
            errores.append(f"Producto con SKU {sku} no encontrado.")
            continue

        # Sumar stock instantáneamente
        await db.productos.update_one({"sku": sku}, {"$inc": {"stock": cantidad}})
        detalles.append({
            "sku": sku,
            "nombre": producto.get("nombre", "N/A"),
            "cantidad_pedida": cantidad,
            "stock_anterior": producto.get("stock", 0),
            "stock_nuevo": producto.get("stock", 0) + cantidad,
            "precio_compra": producto.get("precio_compra", 0),
        })

    # Calcular coste total del pedido
    coste_total = sum(d["cantidad_pedida"] * d["precio_compra"] for d in detalles)
    codigo_pedido = f"ORD-{uuid.uuid4().hex[:6].upper()}"

    pedido = {
        "codigo_pedido": codigo_pedido,
        "codigo_proveedor": codigo_proveedor,
        "nombre_proveedor": proveedor.get("nombre", "N/A"),
        "detalles": detalles,
        "errores": errores,
        "coste_total": coste_total,
        "fecha": datetime.now(timezone.utc).isoformat(),
        "estado": "completado",
    }
    await db.pedidos.insert_one(pedido)

    msg = f"Pedido {codigo_pedido} creado para proveedor {proveedor.get('nombre')} ({codigo_proveedor}). {len(detalles)} producto(s) procesados, stock actualizado instantáneamente."
    if errores:
        msg += f" Errores: {'; '.join(errores)}"
    return {"ok": True, "message": msg, "detalles": detalles}

async def _get_pedidos():
    pedidos = await db.pedidos.find().to_list(length=100)
    for p in pedidos:
        p["_id"] = str(p["_id"])
    return {"pedidos": pedidos, "total": len(pedidos)}

async def _update_pedido(codigo_pedido: str, estado: str):
    valid_estados = ["completado", "recibido", "cancelado"]
    if estado not in valid_estados:
        return {"ok": False, "message": f"Estado inválido '{estado}'. Usa: {', '.join(valid_estados)}"}
    result = await db.pedidos.update_one(
        {"codigo_pedido": codigo_pedido},
        {"$set": {"estado": estado}}
    )
    if result.matched_count == 0:
        return {"ok": False, "message": f"No se encontró el pedido con código {codigo_pedido}."}
    return {"ok": True, "message": f"Pedido {codigo_pedido} actualizado a estado '{estado}'."}

async def _delete_pedido(codigo_pedido: str):
    result = await db.pedidos.delete_one({"codigo_pedido": codigo_pedido})
    if result.deleted_count > 0:
        return {"ok": True, "message": f"Pedido {codigo_pedido} eliminado. Nota: el stock NO se ha revertido."}
    return {"ok": False, "message": f"No se encontró el pedido con código {codigo_pedido}."}


# ── Desechos ──────────────────────────────────────────────────────────────────

async def _get_desechos():
    desechos = await db.desechos.find().to_list(length=100)
    for d in desechos:
        d["_id"] = str(d["_id"])
    return {"desechos": desechos, "total": len(desechos)}

async def _procesar_caducados():
    hoy = datetime.now(timezone.utc).date().isoformat()
    # Find expired products (fecha_caducidad <= hoy)
    caducados = await db.productos.find({"fecha_caducidad": {"$lte": hoy}}).to_list(length=100)
    # Filtrar solo los que realmente tienen fecha_caducidad definida
    caducados = [p for p in caducados if p.get("fecha_caducidad")]
    
    if not caducados:
        return {"ok": True, "message": f"Revisión completada ({hoy}). No hay productos caducados."}
    
    registros = []
    for p in caducados:
        desecho = {
            "producto_nombre": p.get("nombre", "N/A"),
            "sku": p.get("sku", "N/A"),
            "cantidad_desechada": p.get("stock", 0),
            "precio_venta": p.get("precio_venta", 0),
            "precio_compra": p.get("precio_compra", 0),
            "perdida_estimada": p.get("stock", 0) * p.get("precio_compra", p.get("precio_venta", 0)),
            "fecha_caducidad": p.get("fecha_caducidad"),
            "fecha_baja": hoy,
            "motivo": "Caducado",
            "categoria": p.get("categoria", "N/A"),
        }
        await db.desechos.insert_one(desecho)
        await db.productos.delete_one({"_id": p["_id"]})
        registros.append(f"{p.get('nombre')} (SKU: {p.get('sku')}, {p.get('stock', 0)} uds)")
        
    return {
        "ok": True,
        "message": f"Revisión completada ({hoy}). {len(caducados)} producto(s) caducados eliminados del inventario y registrados como desecho: {', '.join(registros)}."
    }


# ── Estadísticas ──────────────────────────────────────────────────────────────

async def _get_estadisticas(tipo="stock_categoria"):
    if tipo == "stock_categoria":
        pipeline = [
            {"$group": {"_id": "$categoria", "total_stock": {"$sum": "$stock"}}}
        ]
        results = await db.productos.aggregate(pipeline).to_list(length=100)
        labels = [r["_id"] if r["_id"] else "Sin Categoría" for r in results]
        values = [r["total_stock"] for r in results]
        return {"labels": labels, "values": values, "tipo": "bar", "titulo": "Stock por Categoría"}

    elif tipo == "top_productos_stock":
        pipeline = [
            {"$sort": {"stock": -1}},
            {"$limit": 10},
            {"$project": {"nombre": 1, "sku": 1, "stock": 1, "_id": 0}}
        ]
        results = await db.productos.aggregate(pipeline).to_list(length=10)
        labels = [f"{r['nombre']} ({r.get('sku', '')})" for r in results]
        values = [r["stock"] for r in results]
        return {"labels": labels, "values": values, "tipo": "bar", "titulo": "Top 10 Productos con Más Stock"}

    elif tipo == "pedidos_mes":
        pipeline = [
            {"$addFields": {"fecha_date": {"$substr": ["$fecha", 0, 7]}}},
            {"$group": {"_id": "$fecha_date", "total_pedidos": {"$sum": 1}, "coste_total": {"$sum": "$coste_total"}}},
            {"$sort": {"_id": 1}}
        ]
        results = await db.pedidos.aggregate(pipeline).to_list(length=100)
        labels = [r["_id"] if r["_id"] else "N/A" for r in results]
        values = [r["total_pedidos"] for r in results]
        costes = [r.get("coste_total", 0) for r in results]
        if not labels:
            return {"labels": ["Sin datos"], "values": [0], "tipo": "bar", "titulo": "Pedidos por Mes"}
        return {"labels": labels, "values": values, "costes": costes, "tipo": "bar", "titulo": "Pedidos por Mes"}

    elif tipo == "perdidas_desechos":
        pipeline = [
            {"$group": {
                "_id": None,
                "total_perdida": {"$sum": "$perdida_estimada"},
                "total_unidades": {"$sum": "$cantidad_desechada"},
                "num_registros": {"$sum": 1}
            }}
        ]
        results = await db.desechos.aggregate(pipeline).to_list(length=1)
        if results:
            r = results[0]
            return {
                "labels": ["Pérdida Económica (€)", "Unidades Desechadas", "Registros"],
                "values": [r.get("total_perdida", 0), r.get("total_unidades", 0), r.get("num_registros", 0)],
                "tipo": "bar",
                "titulo": "Pérdidas por Desechos"
            }
        return {"labels": ["Sin datos"], "values": [0], "tipo": "bar", "titulo": "Pérdidas por Desechos"}
    
    return {"error": f"Tipo de estadística '{tipo}' no soportado. Usa: stock_categoria, top_productos_stock, pedidos_mes, perdidas_desechos."}
