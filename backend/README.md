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
WALLET_DB_PATH=wallet.db
```

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `WALLET_API_BASE_URL` | No | URL base de la API W1. Por defecto apunta al mock. |
| `WALLET_DOCUMENT_KEY` | Sí | Clave de firma HMAC para W1. No la subas al repositorio. |
| `ONBOARDING_SESSION_TTL_SECONDS` | No | Tiempo de vida de la sesión de onboarding en segundos. |
| `WALLET_DB_PATH` | No | Archivo SQLite donde se registran las verificaciones de wallet. Por defecto `wallet.db`; una ruta relativa se resuelve respecto a `backend/`. |
| `COPILOT_MODEL` | No | Modelo de lenguaje del asistente. Por defecto `gpt-6-luna`. |
| `COPILOT_USE_LOGGED_IN_USER` | No | `true` (por defecto) usa la sesión local del CLI de Copilot. Con `false` el SDK exige un token en el entorno. |
| `COPILOT_REASONING_EFFORT` | No | Esfuerzo de razonamiento. Por defecto `low`. Con `gpt-6-luna` valen `low`, `medium`, `high` y `xhigh`; `minimal` se rechaza. |
| `COPILOT_TIMEOUT_SECONDS` | No | Tiempo máximo de espera de una respuesta. Por defecto `60`. |

Las variables ya definidas en el entorno tienen prioridad sobre `.env`.

### Asistente con Copilot

El asistente del chat usa el SDK de GitHub Copilot (`github-copilot-sdk`) con la sesión local del CLI de Copilot: antes de arrancar el backend, inicia sesión en Copilot en esta máquina (`copilot` y `/login`). No hace falta token mientras el backend corra con tu usuario. El modelo solo genera texto: no tiene herramientas ni permisos sobre archivos o comandos.

El texto que el usuario escribe en el chat se envía a Copilot. Los datos registrados de la wallet no se le envían.

El asistente se expone en `POST /assistant` (protocolo AG-UI), junto al agente del formulario en `/agent`; cada uno tiene su propio estado. Si el usuario pide sus datos registrados, una tool los obtiene y la aplicación los muestra con un formato fijo, con todos los campos salvo el identificador de verificación (`kyc_id`).

- **Alcance por sesión:** solo se muestra la wallet registrada en la sesión actual (el `thread_id` que fija el servidor). Un DNI u otro dato escrito en el chat no sirve para ver datos de otra persona.
- **Limitación:** el vínculo entre la sesión y la wallet vive en memoria. Tras reiniciar el backend, o en una sesión nueva, el asistente responde que todavía no hay datos registrados.
- **Si Copilot no responde:** el chat avisa de que el asistente no está disponible y el formulario sigue funcionando.

## 3. Base de datos de wallets

Al arrancar, el backend crea el archivo SQLite (`WALLET_DB_PATH`) con la tabla `wallets` si no existe. Cada vez que la API KYC responde a la activación se guarda un registro con el estado devuelto (`ACTIVE`, `PENDING` o `REJECTED`); solo `ACTIVE` activa la wallet. Si la API no responde, no se guarda nada.

| Columna | Descripción |
|---------|-------------|
| `kyc_id` | Clave primaria: `id` de la verificación KYC. |
| `wallet_id` | Identificador de la wallet devuelto por la API. |
| `state` | Estado devuelto por la API. |
| `document_number` | DNI. |
| `document_type` | Tipo de documento, `TEST` por defecto. |
| `name`, `last_name` | Nombre y apellidos. |
| `phone`, `email` | Teléfono y correo. |
| `max_amount` | Monto máximo por operación, como texto decimal. |

El archivo `.db` contiene datos personales en claro y no se versiona (`*.db` está en `.gitignore`). Para consultarlo:

```powershell
.venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.connect('wallet.db').execute('SELECT * FROM wallets').fetchall())"
```

## 4. Arrancar el servidor

```powershell
.venv\Scripts\python.exe -m uvicorn server:app --port 8000
```

El servidor queda en `http://localhost:8000`. El endpoint del agente es `/agent`. Debe estar levantado antes del frontend (`http://localhost:4200`).

Si el puerto 8000 está ocupado, busca el proceso con `Get-NetTCPConnection -LocalPort 8000 -State Listen` y ciérralo con `Stop-Process -Id <PID>`.

## 5. Ejecutar los tests

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Estructura

- `domain/`: reglas de negocio (validación de pasos, TTL).
- `application/`: servicio de onboarding (activación y registro).
- `ports/`: interfaces hacia servicios externos (`WalletGateway`, `WalletRepository`, `ConversationalModel`, `SessionWalletLookup`).
- `adapters/`: LangGraph (onboarding y asistente), tools `activate_wallet` y `get_my_wallet_data`, endpoints AG-UI/FastAPI, cliente de la API W1, repositorio SQLite y modelo de Copilot.
- `tests/`: pruebas unitarias y de integración.
- `server.py`: punto de entrada que compone las dependencias.
