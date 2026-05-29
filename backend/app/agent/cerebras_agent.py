# backend/app/agent/cerebras_agent.py
#
# ARQUITECTURA MULTI-AGENTE: Cadena secuencial de 3 LLMs (Cerebras)
# Usando el SDK oficial de openai compatible con la API de Cerebras.
#
#   Usuario ──► [Router]  ──► [Executor]  ──► [Formatter] ──► Frontend
#               llama3.1-8b    llama3.1-70b    llama3.1-8b
#               (analiza)      (tools/DB)      (empaqueta JSON)
#

import os
import json
from openai import OpenAI
from app.agent.tools import TOOLS_DEFINITIONS, execute_tool

# ── Configuración ─────────────────────────────────────────────────────────────
client = OpenAI(
    base_url="https://api.cerebras.ai/v1",
    api_key=os.environ.get("CEREBRAS_API_KEY")
)

# Modelos asignados a cada rol de la cadena
ROUTER_MODEL    = "zai-glm-4.7"
EXECUTOR_MODEL  = "gpt-oss-120b"
FORMATTER_MODEL = "zai-glm-4.7"


# ── System Prompts de cada agente ─────────────────────────────────────────────

ROUTER_PROMPT = """
Eres el ROUTER de un sistema ERP multi-agente. Tu trabajo es analizar la petición
del usuario y convertirla en una orden técnica clara y directa para el siguiente
agente (el Executor).

Herramientas disponibles:
- PRODUCTOS: get_productos, create_producto, update_producto (por SKU), delete_producto (por SKU)
- PROVEEDORES: get_proveedores, create_proveedor, update_proveedor (por codigo_proveedor), delete_proveedor (por codigo_proveedor)
- PEDIDOS: create_pedido (codigo_proveedor + lista 'SKU:cantidad'), get_pedidos, update_pedido (por codigo_pedido), delete_pedido (por codigo_pedido)
- DESECHOS: procesar_caducados, get_desechos
- ESTADÍSTICAS: get_estadisticas con tipo='stock_categoria' | 'top_productos_stock' | 'pedidos_mes' | 'perdidas_desechos'

Reglas CRÍTICAS:
- Identifica la INTENCIÓN del usuario: ¿ver?, ¿crear?, ¿actualizar?, ¿borrar?, ¿estadísticas?, ¿caducados?
- Identifica la ENTIDAD: productos, proveedores, pedidos, desechos o estadísticas.
- Si el usuario pide crear, añadir o registrar un PROVEEDOR, tu intención debe apuntar OBLIGATORIAMENTE a create_proveedor. NUNCA uses la herramienta de lectura (get_proveedores) si el usuario pide crear.
- Si el usuario pide crear un PRODUCTO, tu intención debe ser create_producto.
- Si el usuario pide crear un PEDIDO, tu intención debe ser create_pedido.

- Redacta una orden concisa y sin ambigüedad. Ejemplos:
  • "Ejecuta get_productos sin filtros y devuelve todos los datos."
  • "Ejecuta create_producto con nombre='Arroz 1kg', stock=200, precio_venta=1.50, fecha_caducidad='2026-12-31'"
  • "Ejecuta update_producto con sku='PROD-ABC123', stock=500"
  • "Ejecuta delete_producto con sku='PROD-ABC123'"
  • "Ejecuta create_proveedor con nombre='DistribucionesXYZ', contacto_email='xyz@email.com'"
  • "Ejecuta update_proveedor con codigo_proveedor='PROV-ABC...', nombre='Nuevo Nombre'"
  • "Ejecuta delete_proveedor con codigo_proveedor='PROV-ABC...'"
  • "Ejecuta create_pedido con codigo_proveedor='PROV-ABC...', productos=['PROD-ABC123:50', 'PROD-DEF456:20']"
  • "Ejecuta update_pedido con codigo_pedido='ORD-123...', estado='completado'"
  • "Ejecuta delete_pedido con codigo_pedido='ORD-123...'"
  • "Ejecuta get_estadisticas con tipo='top_productos_stock'"
  • "Ejecuta procesar_caducados para revisar productos vencidos."
- Si el usuario pide crear algo pero NO proporciona todos los datos necesarios,
  genera una orden que diga: "SOLICITAR_FORMULARIO para [entidad] con campos: [lista de campos]"
- Responde SOLAMENTE con la orden técnica. Nada más.
"""

EXECUTOR_PROMPT = """
CRÍTICO: ERES UN SISTEMA DE EJECUCIÓN INVISIBLE. TIENES TOTALMENTE PROHIBIDO HABLAR O RESPONDER CON TEXTO NORMAL. TU ÚNICA FORMA DE SALIDA ES EJECUTAR UNA HERRAMIENTA (TOOL CALL). Si el Router te pide crear, ejecuta create_producto inmediatamente sin pedir confirmaciones ni formularios.

Eres un agente de base de datos ERP autónomo. TIENES que usar las herramientas proporcionadas para crear, leer, actualizar o borrar datos. NUNCA pidas al usuario que rellene formularios ni delegues la tarea. Si te piden crear algo, usa la herramienta de creación inmediatamente.

Reglas:
- Extrae y utiliza ESTRICTAMENTE los argumentos enviados por el Router. NUNCA inventes nombres genéricos como 'Nuevo Producto' ni cantidades fijas como 100. Si falta información, infiérela del contexto pero no sobreescribas con valores "hardcodeados".
- Después de ejecutar una herramienta, devuelve los datos RAW tal como los recibes.
  No los formatees ni los interpretes. Solo pasa los datos.

CRITICAL: You must ONLY return the exact data provided by the tools. If a tool returns an empty list or 0 results, you MUST return an empty list. NEVER invent, hallucinate, or mock data (like 'Harina' or 'Aceite').
"""

FORMATTER_PROMPT = """
Eres el FORMATTER de un sistema ERP multi-agente. Recibes datos crudos del Executor
y los empaquetas en el JSON exacto que espera el frontend.

Tu ÚNICO formato de respuesta es un objeto JSON válido con esta estructura:

{
  "action": "show_table" | "show_form" | "show_chart" | "show_message" | "confirm_delete",
  "entity": "productos" | "proveedores" | "pedidos" | "desechos" | "estadisticas" | null,
  "data": [...],
  "message": "Texto explicativo para el usuario en español",
  "form_fields": [...],
  "chart_type": "bar" | "pie" | "line" | null
}

Reglas:
- Si los datos contienen una lista de registros, usa action="show_table" y pon los registros en "data".
- Si los datos contienen labels/values (estadísticas), usa action="show_chart" e indica chart_type.
- Si los datos dicen FORMULARIO|entidad|campos, usa action="show_form" y llena form_fields con los campos.
- Si los datos dicen CONFIRMACION|entidad|id, usa action="confirm_delete" con un mensaje descriptivo.
- Si los datos son un mensaje de éxito/error simple, usa action="show_message".
- Responde SOLAMENTE con el JSON. Nada de texto adicional fuera del JSON.

CRÍTICO: Cuando muestres listas de datos (productos, pedidos, proveedores, desechos, etc.), NUNCA respondas solo con un resumen como "Hay 3 productos" o "Se encontró 1 pedido". DEBES mostrar los detalles de CADA elemento en el campo "message" usando un formato de viñetas limpio y estructurado con saltos de línea (\\n).

Formato obligatorio para PRODUCTOS:
📦 **[Nombre del Producto]**\\n   - SKU: [SKU]\\n   - Stock: [Stock] uds\\n   - Precio venta: [Precio]€\\n   - Caducidad: [Fecha]\\n\\n

Formato obligatorio para PEDIDOS:
📋 **Pedido [ID]**\\n   - Proveedor: [Proveedor]\\n   - Productos: [lista de SKU:cantidad]\\n   - Coste total: [Coste]€\\n   - Estado: [Estado]\\n   - Fecha: [Fecha]\\n\\n

Formato obligatorio para PROVEEDORES:
🏢 **[Nombre del Proveedor]**\\n   - ID: [ID]\\n   - Email: [Contacto]\\n   - Teléfono: [Teléfono]\\n   - País: [País]\\n\\n

Formato obligatorio para DESECHOS:
🗑️ **[Nombre del Producto]**\\n   - SKU: [SKU]\\n   - Unidades desechadas: [Cantidad]\\n   - Pérdida estimada: [Pérdida]€\\n   - Fecha caducidad: [Fecha]\\n   - Fecha baja: [Fecha baja]\\n\\n

Siempre incluye una línea introductoria antes de la lista, por ejemplo:
"Aquí tienes los 3 productos registrados:\\n\\n📦 **Aceite 1L**\\n   - SKU: P001\\n   - Stock: 50 uds\\n   - Precio: 3.50€\\n\\n📦 **Arroz 1kg**\\n..."

CRITICAL: You must ONLY format the exact data provided by the Executor. If the database returns an empty list, you MUST return an empty list. NEVER invent, hallucinate, or mock data (like 'Harina' or 'Aceite').
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _error_response(agent_name: str, error_msg: str) -> dict:
    """Devuelve un JSON estructurado para errores, compatible con el frontend."""
    return {
        "action": "show_message",
        "entity": None,
        "data": [],
        "message": f"⚠️ Error en {agent_name}: {error_msg}",
        "form_fields": [],
        "chart_type": None,
    }


def _parse_json_response(raw_text: str) -> dict:
    """Intenta parsear JSON desde la respuesta del modelo, limpiando markdown."""
    text = raw_text.strip() if raw_text else ""
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "action": "show_message",
            "entity": None,
            "data": [],
            "message": text,
            "form_fields": [],
            "chart_type": None,
        }


# ── Clase principal ───────────────────────────────────────────────────────────

class CerebrasAgent:
    """
    Sistema Multi-Agente: cadena secuencial de 3 LLMs usando Cerebras.
    Router (llama3.1-8b) → Executor (llama3.1-70b) → Formatter (llama3.1-8b)
    """

    async def run(self, message: str, history: list[dict]) -> dict:
        """
        Ejecuta la cadena multi-agente.
        """

        # ══════════════════════════════════════════════════════════════════════
        # PASO 1: ROUTER — Analiza la intención y genera una orden técnica
        # ══════════════════════════════════════════════════════════════════════
        try:
            router_messages = [{"role": "system", "content": ROUTER_PROMPT}]
            # Para el router pasamos el histórico para contexto, y luego el mensaje actual
            for m in history:
                role = "assistant" if m["role"] == "model" else m["role"]
                router_messages.append({"role": role, "content": m["content"]})
            router_messages.append({"role": "user", "content": f"Petición del usuario: {message}"})

            router_response = client.chat.completions.create(
                model=ROUTER_MODEL,
                messages=router_messages,
                temperature=0.0
            )
            msg_content = router_response.choices[0].message.content
            router_order = msg_content.strip() if msg_content else ""

        except Exception as e:
            return _error_response("Router", f"{type(e).__name__}: {str(e)}")

        # ══════════════════════════════════════════════════════════════════════
        # PASO 2: EXECUTOR — Ejecuta herramientas según la orden del Router
        # ══════════════════════════════════════════════════════════════════════
        try:
            executor_messages = [
                {"role": "system", "content": EXECUTOR_PROMPT},
                {"role": "user", "content": f"Orden del Router: {router_order}"}
            ]

            tc = "required"
            # Forzar herramienta específica si el Router la menciona explícitamente
            forced_tools = [
                "create_producto", "update_producto", "delete_producto", "get_productos",
                "create_proveedor", "update_proveedor", "delete_proveedor", "get_proveedores",
                "create_pedido", "get_pedidos", "update_pedido", "delete_pedido",
                "get_desechos", "procesar_caducados", "get_estadisticas",
            ]
            order_lower = router_order.lower()
            for tool_name in forced_tools:
                if tool_name in order_lower:
                    tc = {"type": "function", "function": {"name": tool_name}}
                    break

            executor_response = client.chat.completions.create(
                model=EXECUTOR_MODEL,
                messages=executor_messages,
                tools=TOOLS_DEFINITIONS,
                tool_choice=tc,
                temperature=0.0
            )
            
            response_message = executor_response.choices[0].message
            
            # Function Calling
            if response_message.tool_calls:
                executor_messages.append(response_message)
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    tool_output = await execute_tool(function_name, function_args)
                    
                    # Convertimos ObjectIds a string si hay en tool_output (manejado en json.dumps via default=str, pero por si acaso)
                    executor_messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(tool_output, default=str),
                    })
                
                # Segunda llamada con los resultados de las tools
                second_response = client.chat.completions.create(
                    model=EXECUTOR_MODEL,
                    messages=executor_messages,
                    temperature=0.0,
                )
                msg_content = second_response.choices[0].message.content
                executor_data = msg_content.strip() if msg_content else ""
            else:
                msg_content = response_message.content
                executor_data = msg_content.strip() if msg_content else ""

        except Exception as e:
            return _error_response("Executor", f"{type(e).__name__}: {str(e)}")

        # ══════════════════════════════════════════════════════════════════════
        # PASO 3: FORMATTER — Empaqueta los datos en el JSON del frontend
        # ══════════════════════════════════════════════════════════════════════
        try:
            # Aseguramos que la respuesta sea JSON usando response_format si está soportado (Cerebras lo soporta en muchos modelos, pero por precaución pedimos JSON en el prompt)
            formatter_response = client.chat.completions.create(
                model=FORMATTER_MODEL,
                messages=[
                    {"role": "system", "content": FORMATTER_PROMPT},
                    {"role": "user", "content": f"Datos del Executor:\n{executor_data}\n\nContexto original del usuario: {message}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            msg_content = formatter_response.choices[0].message.content
            raw_json = msg_content.strip() if msg_content else ""

        except Exception as e:
            return _error_response("Formatter", f"{type(e).__name__}: {str(e)}")

        # Parsea el JSON final del Formatter
        return _parse_json_response(raw_json)
