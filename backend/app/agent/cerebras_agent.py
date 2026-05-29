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

Reglas:
- Identifica la INTENCIÓN del usuario: ¿quiere ver datos?, ¿crear algo?, ¿borrar?, ¿estadísticas?
- Identifica la ENTIDAD: productos, proveedores, pedidos, desechos o estadísticas.
- Redacta una orden concisa y sin ambigüedad. Ejemplos:
  • "Ejecuta get_productos sin filtros y devuelve todos los datos."
  • "Ejecuta create_producto con nombre='Arroz 1kg', sku='P010', stock=200, precio_venta=1.50"
  • "Ejecuta get_estadisticas con tipo='stock_categoria'"
  • "Ejecuta procesar_caducados para revisar productos vencidos."
- Si el usuario pide crear algo pero NO proporciona todos los datos necesarios,
  genera una orden que diga: "SOLICITAR_FORMULARIO para [entidad] con campos: [lista de campos]"
- Si el usuario pide eliminar algo, genera: "SOLICITAR_CONFIRMACION para eliminar [entidad] con [identificador]"
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
📦 **[Nombre del Producto]**\\n   - SKU: [SKU]\\n   - Stock: [Stock] uds\\n   - Precio: [Precio]€\\n\\n

Formato obligatorio para PEDIDOS:
📋 **Pedido [ID]**\\n   - Proveedor: [Proveedor]\\n   - Producto: [Producto]\\n   - Cantidad: [Cantidad] uds\\n   - Estado: [Estado]\\n   - Fecha: [Fecha]\\n\\n

Formato obligatorio para PROVEEDORES:
🏢 **[Nombre del Proveedor]**\\n   - ID: [ID]\\n   - Contacto: [Contacto]\\n   - Teléfono: [Teléfono]\\n\\n

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
    text = raw_text.strip()
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
            router_order = router_response.choices[0].message.content.strip()

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
            if "create_producto" in router_order.lower():
                tc = {"type": "function", "function": {"name": "create_producto"}}

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
                    temperature=0.0
                )
                executor_data = second_response.choices[0].message.content.strip()
            else:
                executor_data = response_message.content.strip()

        except Exception as e:
            return _error_response("Executor", f"{type(e).__name__}: {str(e)}")

        # ══════════════════════════════════════════════════════════════════════
        # PASO 3: FORMATTER — Empaqueta los datos en el JSON del frontend
        # ══════════════════════════════════════════════════════════════════════
        try:
            formatter_messages = [
                {"role": "system", "content": FORMATTER_PROMPT},
                {"role": "user", "content": f"Datos del Executor:\n{executor_data}\n\nContexto original del usuario: {message}"}
            ]
            
            # Aseguramos que la respuesta sea JSON usando response_format si está soportado (Cerebras lo soporta en muchos modelos, pero por precaución pedimos JSON en el prompt)
            formatter_response = client.chat.completions.create(
                model=FORMATTER_MODEL,
                messages=formatter_messages,
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw_json = formatter_response.choices[0].message.content.strip()

        except Exception as e:
            return _error_response("Formatter", f"{type(e).__name__}: {str(e)}")

        # Parsea el JSON final del Formatter
        return _parse_json_response(raw_json)
