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

Las variables ya definidas en el entorno tienen prioridad sobre `.env`.

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
- `ports/`: interfaces hacia servicios externos (`WalletGateway`, `WalletRepository`).
- `adapters/`: LangGraph, tool `activate_wallet`, endpoint AG-UI/FastAPI, cliente de la API W1 y repositorio SQLite.
- `tests/`: pruebas unitarias y de integración.
- `server.py`: punto de entrada que compone las dependencias.
