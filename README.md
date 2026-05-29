<![CDATA[<div align="center">

# 🏪 Stock Atelier

### ERP Inteligente controlado por Lenguaje Natural

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Cerebras](https://img.shields.io/badge/Cerebras_AI-LLM-FF6B35?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDJMMiAyMmgyMEwxMiAyeiIgZmlsbD0id2hpdGUiLz48L3N2Zz4=&logoColor=white)](https://cerebras.ai/)

*Prototipo de ERP para la asignatura Sistemas de la Información Empresarial (UMA)*
*Traduce instrucciones en lenguaje natural a operaciones CRUD sobre la base de datos mediante agentes LLM.*

---

</div>

## 📖 Descripción

**Stock Atelier** es un sistema ERP (Enterprise Resource Planning) asistido por Inteligencia Artificial que permite gestionar el inventario, proveedores, pedidos de compra y control de caducidades de un negocio **usando únicamente lenguaje natural**.

En lugar de formularios tradicionales, el usuario escribe peticiones en un chat conversacional — *"Crea un producto llamado Aceite 1L con 50 unidades a 3,50€"* — y una **cadena de 3 agentes LLM** (Router → Executor → Formatter) se encarga de interpretar la intención, ejecutar la operación correspondiente en MongoDB y devolver la respuesta formateada al frontend.

---

## ✨ Características Principales

| Módulo | Funcionalidad |
|---|---|
| **📦 Productos** | CRUD completo con autogeneración de SKU (`PROD-XXXXXX`), control de stock, precios y fechas de caducidad. |
| **🏢 Proveedores** | Alta, consulta, modificación y baja con código autogenerado (`PROV-XXXXXX`). |
| **📋 Pedidos** | Creación de pedidos vinculados a proveedores con **integridad referencial**, suma instantánea de stock y código de pedido automático (`ORD-XXXXXX`). |
| **🗑️ Desechos** | Procesamiento automático de productos caducados: los elimina del inventario y registra la pérdida económica. |
| **📊 Estadísticas** | Stock por categoría, top 10 productos, pedidos por mes y pérdidas acumuladas por desechos. |
| **📈 Dashboard** | Panel lateral en tiempo real con tablas de productos, proveedores y últimos pedidos que se actualiza tras cada operación. |
| **💬 Chat con IA** | Interfaz conversacional con botones de acceso rápido, historial de contexto y respuestas formateadas con viñetas. |

---

## 🧠 Arquitectura Multi-Agente

El sistema utiliza una **cadena secuencial de 3 modelos LLM** de Cerebras AI, cada uno con un rol especializado:

```
┌──────────┐      ┌───────────┐      ┌───────────┐
│  Router  │ ───► │ Executor  │ ───► │ Formatter │
│ zai-glm  │      │ gpt-oss   │      │ zai-glm   │
│  4.7     │      │  120b     │      │  4.7      │
└──────────┘      └───────────┘      └───────────┘
  Analiza            Ejecuta           Empaqueta
  intención          tools/DB          JSON → UI
```

1. **Router** — Analiza la petición del usuario y genera una orden técnica inequívoca.
2. **Executor** — Recibe la orden y ejecuta la herramienta (Function Calling) correspondiente contra MongoDB.
3. **Formatter** — Toma los datos crudos y los empaqueta en un JSON estructurado que el frontend renderiza.

---

## 🛠️ Stack Tecnológico

### Frontend
| Tecnología | Versión | Uso |
|---|---|---|
| **React** | 19.x | Librería de UI |
| **Vite** | 8.x | Bundler y dev server |
| **Tailwind CSS** | 4.x | Framework de estilos utility-first |

### Backend
| Tecnología | Versión | Uso |
|---|---|---|
| **FastAPI** | 0.115 | Framework web asíncrono |
| **Python** | 3.12 | Lenguaje del servidor |
| **Motor** | 3.6 | Driver asíncrono para MongoDB |
| **Pydantic** | 2.5 | Validación de datos |
| **OpenAI SDK** | latest | Cliente compatible con la API de Cerebras |

### Infraestructura
| Tecnología | Uso |
|---|---|
| **Docker & Docker Compose** | Orquestación de los 3 servicios (MongoDB, Backend, Frontend) |
| **MongoDB 7** | Base de datos NoSQL |
| **Cerebras AI** | Proveedor de modelos LLM (zai-glm-4.7, gpt-oss-120b) |

---

## 📋 Requisitos Previos

Antes de empezar, asegúrate de tener instalado:

- **Docker** (v20.10+) y **Docker Compose** (v2+)
  - 📥 [Instalar Docker Desktop](https://docs.docker.com/get-docker/)
- **API Key de Cerebras AI**
  - 🔑 [Obtener clave en cerebras.ai](https://cloud.cerebras.ai/)

> [!NOTE]
> No necesitas instalar Python, Node.js ni MongoDB en tu máquina. Docker se encarga de todo.

---

## 🚀 Instalación y Ejecución

### Paso 1 — Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/chatbotERP.git
cd chatbotERP
```

### Paso 2 — Configurar las variables de entorno

Crea el archivo `.env` dentro de la carpeta `backend/`:

```bash
touch backend/.env
```

Abre el archivo y añade tu clave de API de Cerebras:

```env
# backend/.env
CEREBRAS_API_KEY=tu_clave_de_cerebras_aqui
```

> [!IMPORTANT]
> El archivo `.env` está incluido en `.gitignore` y **nunca** se sube al repositorio. Cada usuario debe crear el suyo con su propia API Key.

### Paso 3 — Levantar el proyecto con Docker

```bash
docker-compose up --build -d
```

Este comando construye las imágenes y levanta los 3 contenedores en segundo plano:

| Servicio | Contenedor | Puerto |
|---|---|---|
| MongoDB | `mongodb` | `27017` |
| Backend (FastAPI) | `backend` | `8000` |
| Frontend (React) | `frontend` | `5173` |

### Paso 4 — Acceder a la aplicación

| Recurso | URL |
|---|---|
| 🖥️ **Frontend (Chat + Dashboard)** | [http://localhost:5173](http://localhost:5173) |
| 📡 **Backend API (Swagger/OpenAPI)** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| ❤️ **Health Check** | [http://localhost:8000/api/health](http://localhost:8000/api/health) |

---

## 💬 Ejemplos de Uso

Una vez abierta la aplicación en el navegador, puedes escribir en el chat instrucciones como:

```
📦 Productos
├── "Crea un producto llamado Aceite de Oliva 1L con 200 unidades, precio 4.50€ y caducidad 2027-06-15"
├── "Muéstrame todos los productos"
├── "Actualiza el stock del producto PROD-ABC123 a 500 unidades"
└── "Elimina el producto con SKU PROD-ABC123"

🏢 Proveedores
├── "Registra un proveedor llamado Distribuciones García con email garcia@email.com"
└── "Lista todos los proveedores"

📋 Pedidos
├── "Haz un pedido al proveedor PROV-ABC123 de 50 unidades de PROD-DEF456"
└── "Muestra todos los pedidos"

🗑️ Desechos
└── "Revisa los productos caducados"

📊 Estadísticas
├── "Muéstrame las estadísticas de stock por categoría"
└── "¿Cuáles son las pérdidas por desechos?"
```

---

## 📁 Estructura del Proyecto

```
chatbotERP/
├── docker-compose.yml          # Orquestación de servicios
├── README.md                   # Este archivo
├── .gitignore
│
├── backend/
│   ├── Dockerfile              # Imagen Python 3.12
│   ├── requirements.txt        # Dependencias Python
│   ├── .env                    # 🔒 Variables de entorno (no versionado)
│   └── app/
│       ├── main.py             # FastAPI: endpoints y CORS
│       └── agent/
│           ├── cerebras_agent.py   # Cadena multi-agente (Router → Executor → Formatter)
│           └── tools.py            # Definiciones de herramientas + lógica MongoDB
│
└── frontend/
    ├── Dockerfile              # Imagen Node 20
    ├── package.json            # Dependencias React/Vite/Tailwind
    └── src/
        └── App.jsx             # Componente principal (Chat + Dashboard)
```

---

## 🔌 API Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/chat` | Envía un mensaje al sistema multi-agente y recibe la respuesta estructurada |
| `GET` | `/api/dashboard` | Devuelve los datos actuales de productos, proveedores y pedidos para el dashboard |
| `GET` | `/api/health` | Comprobación del estado del servicio y los modelos activos |

---

## 🛑 Detener el Proyecto

```bash
docker-compose down
```

Para detener **y eliminar los datos** de la base de datos:

```bash
docker-compose down -v
```

---

## 👥 Autores

Desarrollado como práctica de la asignatura **Sistemas de la Información Empresarial** — Universidad de Málaga (UMA), curso 2025/2026.

---

<div align="center">

*Hecho con ☕ y mucha IA*

</div>
]]>
