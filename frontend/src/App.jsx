import { useState, useRef, useEffect } from "react";

// ── Configuración ─────────────────────────────────────────────────────────────
const API_URL = "http://localhost:8000/api/chat";

const MODELS = [
  { id: "zai-glm-4.7",   label: "ZAI GLM 4.7",   badge: "Fast" },
  { id: "gpt-oss-120b",  label: "GPT OSS 120B",  badge: "Smart" },
];

// ── Componentes de UI ─────────────────────────────────────────────────────────

function Bubble({ msg }) {
  const isUser = msg.role === "user";
  
  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="bg-cyan-500 text-slate-900 px-4 py-3 rounded-2xl rounded-tr-sm max-w-[70%] shadow-sm">
          <p className="text-sm font-medium">{msg.content}</p>
        </div>
      </div>
    );
  }

  // Mensaje del sistema
  const { parsed, latency, model } = msg;
  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700/50 flex items-center justify-center shrink-0">
        <span className="text-cyan-400 text-xs font-bold">SA</span>
      </div>
      <div className="bg-slate-800/40 border border-slate-700/50 px-4 py-3 rounded-2xl rounded-tl-sm max-w-[80%]">
        {parsed?.message ? (
          <p className="text-sm text-slate-300 leading-relaxed">{parsed.message}</p>
        ) : (
          <p className="text-sm text-slate-300 italic">Procesando respuesta...</p>
        )}
        
        {/* Metadatos */}
        {latency && (
          <div className="mt-2 text-[10px] font-medium text-slate-500 flex items-center gap-2 uppercase tracking-wider">
            <span>{model}</span>
            <span>&bull;</span>
            <span>{latency}ms</span>
          </div>
        )}
      </div>
    </div>
  );
}

function DashboardBlock({ title, children }) {
  return (
    <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5 shadow-sm">
      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">{title}</h3>
      {children}
    </div>
  );
}

// ── App principal ─────────────────────────────────────────────────────────────
export default function App() {
  const [model, setModel] = useState("zai-glm-4.7");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    {
      role: "agent",
      parsed: {
        action: "show_message",
        message: "¡Bienvenido a Stock Atelier! Conectado al motor Cerebras en tiempo real. ¿En qué te puedo ayudar hoy?",
      },
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [liveDashboardData, setLiveDashboardData] = useState([]);
  const bottomRef = useRef(null);

  async function fetchDashboardData() {
    try {
      const res = await fetch("http://localhost:8000/api/dashboard");
      if (res.ok) {
        const data = await res.json();
        if (data.productos) {
          setLiveDashboardData(data.productos);
        }
      }
    } catch (e) {
      console.error("Error fetching dashboard data:", e);
    }
  }

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const apiHistory = messages
    .filter(m => m.role === "user" || (m.role === "agent" && m.raw))
    .map(m => ({ role: m.role === "user" ? "user" : "model", content: m.raw || m.content }));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(overrideText = null) {
    const text = (overrideText || input).trim();
    if (!text || loading) return;

    if (!overrideText) setInput("");
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setLoading(true);

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, model, history: apiHistory }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const { reply, model_used, latency_ms } = await res.json();

      setMessages(prev => [...prev, {
        role: "agent",
        parsed: reply,
        raw: JSON.stringify(reply),
        model: model_used,
        latency: latency_ms,
      }]);

      await fetchDashboardData();
    } catch (err) {
      setMessages(prev => [...prev, {
        role: "agent",
        parsed: { action: "show_message", message: `Error de conexión: ${err.message}` },
      }]);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  // Encontrar el último mensaje con datos de tabla para el Dashboard
  const lastDataMsg = [...messages].reverse().find(m => m.parsed?.data && Array.isArray(m.parsed.data) && m.parsed.data.length > 0);
  const dashboardData = liveDashboardData.length > 0 ? liveDashboardData : (lastDataMsg?.parsed?.data || []);
  
  // Calcular métricas para el resumen (asumiendo datos de productos)
  const isProducts = dashboardData.length > 0 && dashboardData[0].sku;
  const totalItems = dashboardData.length;
  const totalStock = isProducts ? dashboardData.reduce((acc, curr) => acc + (Number(curr.stock) || 0), 0) : 0;
  
  // Calcular el max stock para la barra de progreso
  const maxStock = isProducts ? Math.max(...dashboardData.map(d => Number(d.stock) || 0), 1) : 1;

  const quickCommands = [
    "📦 Mostrar todos los productos",
    "🏢 Listar proveedores",
    "📉 Ver estadísticas de stock",
    "⚠️ Revisar caducados",
  ];

  return (
    <div className="flex h-screen bg-[#0B1120] text-slate-200 font-sans overflow-hidden">
      
      {/* ── Columna Izquierda: Chat (60%) ── */}
      <div className="w-full lg:w-[60%] flex flex-col border-r border-slate-700/50 bg-slate-900 relative">
        
        {/* Cabecera */}
        <header className="px-6 py-4 border-b border-slate-700/50 flex items-center justify-between bg-slate-900/80 backdrop-blur-md z-10">
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse"></span>
              Stock Atelier
            </h1>
            <p className="text-xs text-slate-400 mt-1">ERP Asistido por Cerebras AI</p>
          </div>
          <div className="flex gap-2">
            <span className="px-3 py-1 bg-slate-800 border border-slate-700/50 rounded-full text-xs font-semibold text-cyan-400">
              ⚡ zai-glm-4.7
            </span>
            <span className="px-3 py-1 bg-slate-800 border border-slate-700/50 rounded-full text-xs font-semibold text-purple-400">
              🧠 gpt-oss-120b
            </span>
          </div>
        </header>

        {/* Área de mensajes */}
        <div className="flex-1 overflow-y-auto p-6 scroll-smooth">
          {messages.map((msg, i) => <Bubble key={i} msg={msg} />)}
          
          {loading && (
            <div className="flex gap-3 mb-4">
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700/50 flex items-center justify-center shrink-0">
                <span className="text-cyan-400 text-xs font-bold">SA</span>
              </div>
              <div className="bg-slate-800/40 border border-slate-700/50 px-5 py-4 rounded-2xl rounded-tl-sm flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce"></div>
                <div className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: "0.15s" }}></div>
                <div className="w-1.5 h-1.5 bg-cyan-500 rounded-full animate-bounce" style={{ animationDelay: "0.3s" }}></div>
              </div>
            </div>
          )}
          <div ref={bottomRef} className="h-4" />
        </div>

        {/* Input y sugerencias */}
        <div className="p-6 border-t border-slate-700/50 bg-slate-900/95 backdrop-blur-sm">
          
          <div className="flex gap-2 mb-4 overflow-x-auto pb-2 scrollbar-hide">
            {quickCommands.map((cmd, i) => (
              <button 
                key={i}
                onClick={() => send(cmd.substring(2).trim())}
                className="whitespace-nowrap px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-full text-xs font-medium text-slate-300 transition-colors"
                disabled={loading}
              >
                {cmd}
              </button>
            ))}
          </div>

          <div className="flex gap-3">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Escribe un comando o petición al ERP..."
              disabled={loading}
              className="flex-1 bg-slate-800/50 border border-slate-700/80 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all"
            />
            <button 
              onClick={() => send()} 
              disabled={loading || !input.trim()}
              className="bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-slate-900 font-bold px-6 py-3 rounded-xl transition-colors shadow-[0_0_15px_rgba(6,182,212,0.2)]"
            >
              Enviar
            </button>
          </div>
        </div>
      </div>

      {/* ── Columna Derecha: Dashboard (40%) ── */}
      <div className="hidden lg:flex w-[40%] bg-[#0B1120] p-6 flex-col gap-6 overflow-y-auto">
        
        {/* Bloque 1: Resumen */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-4 flex flex-col justify-center items-center">
            <span className="text-slate-400 text-xs font-semibold uppercase tracking-wider mb-1">Registros</span>
            <span className="text-3xl font-bold text-white">{totalItems}</span>
          </div>
          <div className="bg-slate-800/30 border border-cyan-900/30 rounded-xl p-4 flex flex-col justify-center items-center shadow-[inset_0_0_20px_rgba(6,182,212,0.05)]">
            <span className="text-cyan-500/80 text-xs font-semibold uppercase tracking-wider mb-1">Stock Total</span>
            <span className="text-3xl font-bold text-cyan-400">{totalStock}</span>
          </div>
        </div>

        {/* Bloque 2: Inventario Live */}
        <DashboardBlock title="Datos en Vivo">
          {dashboardData.length > 0 ? (
            <div className="space-y-4">
              {dashboardData.map((item, idx) => {
                const name = item.nombre || item.id || `Item ${idx}`;
                const val = item.stock !== undefined ? Number(item.stock) : (item.total || 0);
                const percent = maxStock > 0 ? Math.min(100, Math.max(2, (val / maxStock) * 100)) : 0;
                
                return (
                  <div key={idx} className="group">
                    <div className="flex justify-between items-end mb-1.5">
                      <span className="text-sm font-medium text-slate-300 truncate pr-4">{name}</span>
                      <span className="text-xs font-bold text-slate-400">{val}</span>
                    </div>
                    {/* Barra de progreso */}
                    <div className="h-1.5 w-full bg-slate-700/50 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-cyan-500 rounded-full transition-all duration-1000 ease-out group-hover:bg-cyan-400"
                        style={{ width: `${percent}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="h-32 flex items-center justify-center border-2 border-dashed border-slate-700/50 rounded-lg">
              <span className="text-sm text-slate-500">No hay datos activos para mostrar</span>
            </div>
          )}
        </DashboardBlock>

        {/* Bloque 3: Guía Rápida */}
        <DashboardBlock title="Guía Rápida">
          <div className="space-y-3 text-sm text-slate-400">
            <p>Puedes usar lenguaje natural para interactuar con el ERP. Algunos ejemplos de lo que puedes pedir:</p>
            <ul className="list-disc pl-5 space-y-2 text-slate-300">
              <li><span className="text-cyan-400">"Crea un producto"</span> llamado Aceite 1L con 50 uds de stock.</li>
              <li><span className="text-cyan-400">"Borra el producto"</span> con SKU P001.</li>
              <li><span className="text-cyan-400">"Haz un pedido"</span> al proveedor prov_001 de 20 uds de P002.</li>
              <li><span className="text-cyan-400">"Dime las estadísticas"</span> de pérdidas por desechos.</li>
            </ul>
          </div>
        </DashboardBlock>

      </div>

    </div>
  );
}
