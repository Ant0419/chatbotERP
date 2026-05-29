# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from app.agent.cerebras_agent import CerebrasAgent

app = FastAPI(title="ERP LLM API — Multi-Agente", version="2.0.0")

# CORS abierto para desarrollo — permite cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Sistema Multi-Agente (usa los 3 modelos en cadena) ────────────────────────
# Router:    zai-glm-4.7       (analiza intención)
# Executor:  gpt-oss-120b      (ejecuta tools)
# Formatter: zai-glm-4.7       (empaqueta JSON)
agent = CerebrasAgent()


# ── Schemas de entrada y salida ───────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str   # "user" | "model"
    content: str

class ChatRequest(BaseModel):
    message: str
    model: str = "multi-agent"               # se ignora, siempre se usan los 3
    history: Optional[list[ChatMessage]] = []

class ChatResponse(BaseModel):
    reply: dict                               # JSON estructurado devuelto por el Formatter
    model_used: str
    latency_ms: float                         # latencia total de la cadena


# ── Endpoint principal ────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    import time
    start = time.perf_counter()

    result = await agent.run(
        message=request.message,
        history=[{"role": m.role, "content": m.content} for m in request.history],
    )

    latency = round((time.perf_counter() - start) * 1000, 2)

    return ChatResponse(
        reply=result,
        model_used="multi-agent (zai-glm-4.7 → gpt-oss-120b → zai-glm-4.7)",
        latency_ms=latency,
    )


# ── Dashboard Data ────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
async def dashboard_data():
    from app.agent.tools import _get_productos, _get_proveedores, _get_pedidos
    productos = await _get_productos()
    proveedores = await _get_proveedores()
    pedidos = await _get_pedidos()
    return {
        "productos": productos.get("productos", []),
        "proveedores": proveedores.get("proveedores", []),
        "pedidos": pedidos.get("pedidos", []),
    }

# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "architecture": "multi-agent (cerebras)",
        "agents": {
            "router": "zai-glm-4.7",
            "executor": "gpt-oss-120b",
            "formatter": "zai-glm-4.7",
        },
    }
