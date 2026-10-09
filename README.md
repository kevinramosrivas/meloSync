# meloSync 🎵
**Gestor y Descargador Inteligente de Música desde YouTube**

Arquitectura moderna y desacoplada construida bajo los principios de **Clean Architecture**, **SOLID** y diseño minimalista inspirado en **Apple Music Dark Mode**:
- **Backend**: FastAPI 0.115+ asíncrono con **WebSockets** para eventos y progreso en tiempo real, streaming HTTP con soporte `Range`, y base de datos SQLite WAL thread-safe con SQLAlchemy 2.0.
- **Frontend**: **Angular 22** (Standalone Components, Signals reactivos, Client WebSocket resiliente, reproductor HTML5 integrado persistente) empaquetado para escritorio con **Tauri v2**.

---

## 🌟 Características Principales

- **Clean Architecture & SOLID**: Separación estricta entre capas:
  - `domain`: Entidades puras (`Track`, `TrackMetadata`, `SearchResult`, `AppSettings`), máquina de estados e interfaces de puertos.
  - `application`: Casos de uso (`SearchYouTube`, `DownloadAndProcessTrack`, `ManageLibrary`, `EditMetadata`, `ManageSettings`) y DTOs tipados.
  - `infrastructure`: SQLite WAL, `yt-dlp`, `ffmpeg` (Loudnorm EBU R128 a -14 LUFS & silencio), iTunes API (carátulas 1000x1000) y `mutagen`.
  - `api / presentation`: Endpoints RESTful con Pydantic v2, gateway WebSocket `/ws/events` y UI Angular 22.
- **Transmisión en Tiempo Real**: WebSocket bidireccional que notifica en vivo cada etapa del pipeline: `PENDIENTE` ➔ `DESCARGANDO` ➔ `PROCESANDO_AUDIO` ➔ `OBTENIENDO_METADATOS` ➔ `COMPLETADA`.
- **Reproductor Web Integrado**: Barra inferior persistente estilo Apple Music con carátula oficial, control de volumen, scrubber interactivo y streaming eficiente con HTTP 206 Range.
- **Ajustes Dinámicos**: Configuración de carpeta de música personalizada, bitrate preferido y nivel de normalización LUFS guardados en base de datos.
- **Soporte Multiplataforma**: Ejecutable como aplicación web en navegador o aplicación de escritorio nativa mediante Tauri v2.

---

## 🏗️ Arquitectura del Sistema

```
meloSync/
├── backend/                      # Backend FastAPI + WebSockets + Clean Architecture
│   ├── src/
│   │   ├── domain/               # Entidades, Enums, Excepciones e Interfaces
│   │   ├── application/          # Casos de uso, DTOs y eventos
│   │   ├── infrastructure/       # SQLite, yt-dlp, FFmpeg, iTunes API, Mutagen
│   │   └── api/                  # FastAPI routers, WebSockets, Worker thread pool
│   ├── tests/                    # Tests automatizados (pytest)
│   ├── requirements.txt          # Dependencias Python
│   └── run.py                    # Servidor local de desarrollo
│
├── frontend/                     # Frontend Angular 22 + Tauri v2
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/             # Servicios Singleton, WebSocket y Reproductor de Audio
│   │   │   ├── domain/           # Modelos TypeScript tipados
│   │   │   ├── data/             # Repositorios y llamadas HTTP a la API
│   │   │   ├── features/         # Vistas Standalone: Search, Downloads, Library, Settings, Metadata
│   │   │   └── shared/           # Sidebar, BottomPlayer, Badges, Pipes, Toasts
│   │   └── styles.css            # Sistema de diseño Apple Music Dark Mode (CSS Puro)
│   ├── src-tauri/                # Configuración nativa de Tauri v2
│   └── package.json
└── README.md
```

---

## 🚀 Guía de Inicio Rápido

### 1. Iniciar el Backend (FastAPI + WebSockets)
```bash
cd backend
pip install -r requirements.txt
python run.py
```
*El servidor estará disponible en `http://127.0.0.1:8000`. La documentación Swagger interactiva se encuentra en `http://127.0.0.1:8000/docs`.*

### 2. Iniciar el Frontend (Angular 22)
```bash
cd frontend
npm install
npm start
```
*Abre tu navegador en `http://localhost:4200` para disfrutar de la experiencia meloSync.*

### 3. Ejecutar Pruebas Automatizadas del Backend
```bash
cd backend
python -m pytest tests -v
```

### 4. Compilar Frontend en Producción
```bash
cd frontend
npm run build
```
