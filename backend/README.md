# Backend de onboarding de wallet

Backend en Python (LangGraph + FastAPI + AG-UI), con arquitectura hexagonal. Requiere **Python 3.13**.

## 1. Instalar dependencias

Desde la carpeta `backend`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Alternativa con `uv`:

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

## 2. Configurar variables de entorno

Crea el archivo `backend/.env` (no se versiona):

```
WALLET_API_BASE_URL=https://bcp-wallet-mock.yefri.workers.dev/groups/6
WALLET_DOCUMENT_KEY=<clave-de-firma>
ONBOARDING_SESSION_TTL_SECONDS=300
```

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `WALLET_API_BASE_URL` | No | URL base de la API W1. Por defecto apunta al mock. |
| `WALLET_DOCUMENT_KEY` | Sí | Clave de firma HMAC para W1. No la subas al repositorio. |
| `ONBOARDING_SESSION_TTL_SECONDS` | No | Tiempo de vida de la sesión de onboarding en segundos. |

Las variables ya definidas en el entorno tienen prioridad sobre `.env`.

## 3. Arrancar el servidor

```powershell
.venv\Scripts\python.exe -m uvicorn server:app --port 8000
```

El servidor queda en `http://localhost:8000`. El endpoint del agente es `/agent`. Debe estar levantado antes del frontend (`http://localhost:4200`).

Si el puerto 8000 está ocupado, busca el proceso con `Get-NetTCPConnection -LocalPort 8000 -State Listen` y ciérralo con `Stop-Process -Id <PID>`.

## 4. Ejecutar los tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Estructura

- `domain/`: reglas de negocio (validación de pasos, TTL).
- `application/`: servicio de onboarding.
- `ports/`: interfaces hacia servicios externos.
- `adapters/`: LangGraph, endpoint AG-UI/FastAPI y cliente de la API W1.
- `tests/`: pruebas unitarias y de integración.
- `server.py`: punto de entrada que compone las dependencias.
