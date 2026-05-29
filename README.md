# Stock Atelier

Un ERP de gestión de inventario controlado por lenguaje natural. En vez de rellenar formularios, le dices al chat lo que necesitas y el sistema se encarga del resto.

Está construido con una arquitectura multi-agente: tres modelos LLM de Cerebras encadenados (Router → Executor → Formatter) que interpretan la petición del usuario, ejecutan la operación contra MongoDB y devuelven la respuesta formateada.

> Práctica 2 de Sistemas de la Información Empresarial — Universidad de Málaga, curso 2025/2026.

---

## Qué hace

- **Productos**: crear, listar, actualizar y borrar. El SKU se genera solo (`PROD-XXXXXX`). Incluye stock, precios y fecha de caducidad.
- **Proveedores**: CRUD completo con código autogenerado (`PROV-XXXXXX`).
- **Pedidos**: se vinculan a un proveedor existente (integridad referencial). El stock se suma automáticamente al crear el pedido. Código autogenerado (`ORD-XXXXXX`).
- **Desechos**: revisa qué productos han caducado, los retira del inventario y registra la pérdida económica.
- **Estadísticas**: stock por categoría, top 10 productos, pedidos por mes y pérdidas acumuladas.
- **Dashboard**: panel lateral que muestra productos, proveedores y pedidos en tiempo real.

---

## Cómo funciona por dentro

```
Usuario ──► Router (zai-glm-4.7) ──► Executor (gpt-oss-120b) ──► Formatter (zai-glm-4.7) ──► Frontend
             analiza intención         ejecuta tools en MongoDB      empaqueta JSON para la UI
```

1. El **Router** lee lo que escribió el usuario y genera una orden técnica clara (ej: "Ejecuta create_producto con nombre='Arroz', stock=100").
2. El **Executor** recibe esa orden y hace Function Calling contra la base de datos.
3. El **Formatter** coge los datos crudos y los mete en un JSON estructurado que el frontend sabe renderizar.

---

## Stack

**Frontend:** React 19 · Vite 8 · Tailwind CSS 4

**Backend:** FastAPI 0.115 · Python 3.12 · Motor 3.6 (async MongoDB)

**Base de datos:** MongoDB 7

**IA:** Cerebras AI (modelos zai-glm-4.7 y gpt-oss-120b, via OpenAI SDK)

**Infra:** Docker + Docker Compose

---

## Requisitos

- Docker y Docker Compose instalados ([descargar](https://docs.docker.com/get-docker/))
- Una API Key de Cerebras ([obtener aquí](https://cloud.cerebras.ai/))

No hace falta tener Python, Node ni MongoDB instalados — Docker monta todo.

---

## Puesta en marcha

**1. Clonar el repo**

```bash
git clone https://github.com/Ant0419/chatbotERP.git
cd chatbotERP
```

**2. Crear el `.env`**

Crea un archivo `backend/.env` con tu clave:

```env
CEREBRAS_API_KEY=tu_clave_aqui
```

> Este archivo está en `.gitignore`, no se sube al repo.

**3. Levantar todo**

```bash
docker-compose up --build -d
```

**4. Abrir en el navegador**

- Frontend: [http://localhost:5173](http://localhost:5173)
- API docs (Swagger): [http://localhost:8000/docs](http://localhost:8000/docs)

Para parar:

```bash
docker-compose down        # mantiene los datos
docker-compose down -v     # borra también la base de datos
```

---

## Ejemplos de lo que puedes escribir en el chat

```
"Crea un producto llamado Aceite de Oliva 1L con 200 unidades, precio 4.50€ y caducidad 2027-06-15"
"Muéstrame todos los productos"
"Registra un proveedor llamado Distribuciones García con email garcia@email.com"
"Haz un pedido al proveedor PROV-ABC123 de 50 unidades de PROD-DEF456"
"Revisa los productos caducados"
"Muéstrame las estadísticas de stock por categoría"
```

---

## Estructura

```
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env                        ← no versionado
│   └── app/
│       ├── main.py                 ← endpoints FastAPI
│       └── agent/
│           ├── cerebras_agent.py   ← cadena multi-agente
│           └── tools.py            ← herramientas + lógica MongoDB
└── frontend/
    ├── Dockerfile
    ├── package.json
    └── src/
        └── App.jsx                 ← chat + dashboard
```

---

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/api/chat` | Envía un mensaje al sistema multi-agente |
| GET | `/api/dashboard` | Datos de productos, proveedores y pedidos |
| GET | `/api/health` | Estado del servicio |
