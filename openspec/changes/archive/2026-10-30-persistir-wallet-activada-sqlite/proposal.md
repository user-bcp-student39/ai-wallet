# Proposal

## Why

Hoy la activación de la wallet llama a la API KYC pero no deja ningún registro propio: solo conserva el `wallet_id` en el estado temporal del grafo (`MemorySaver`), que se pierde al reiniciar el backend. No hay forma de saber qué usuarios activaron su wallet, con qué verificación KYC ni con qué monto máximo.

## What Changes

- La activación final invoca la API `POST /kyc/verifications` mediante una tool de LangChain (`@tool`) llamada desde el grafo de onboarding. La tool delega en el puerto de wallet existente.
- La petición mantiene `documentType: TEST`, `scenario: APPROVED` y `document: TEST-<HMAC(DNI)>`: el DNI real no se envía a la API.
- Se captura de la respuesta de la API el `id` de verificación KYC, el `wallet_id` y el `status`.
- Cada vez que la API responde a la verificación se persiste un registro en una base de datos SQLite, tabla `wallets`, con cualquier estado devuelto (`ACTIVE`, `PENDING` o `REJECTED`). Solo `ACTIVE` activa la wallet para el usuario. Los campos son:
  - `kyc_id` (clave primaria): `id` devuelto por la API.
  - `wallet_id`: `wallet_id` devuelto por la API.
  - `state`: estado de activación devuelto por la API (`ACTIVE`, `PENDING` o `REJECTED`).
  - `document_number`: DNI real.
  - `document_type`: `TEST` por defecto.
  - `name`, `last_name`, `phone`, `email`: datos del onboarding.
  - `max_amount`: monto máximo por operación.
- Si la API no responde o devuelve un error sin `id` de verificación, no se guarda ningún registro: sin `kyc_id` no hay clave primaria.
- Si el guardado en SQLite falla tras responder la API, la activación se informa como error al usuario, con cualquier estado, y no se reintenta automáticamente.
- La interfaz muestra un mensaje final de que la activación no se completó cuando el onboarding termina sin activar la wallet (KYC no aprobada, API no disponible o fallo de registro). No ofrece botón de reintento: repetir la llamada crearía otra wallet en la API.
- La ruta del archivo SQLite se configura con la variable de entorno `WALLET_DB_PATH`.

Fuera de alcance: cifrado en reposo y política de retención de los datos personales, idempotencia ante altas repetidas con el mismo DNI, registrar intentos sin respuesta de la API, reconciliación entre la API y la base de datos, un LLM que decida cuándo invocar la tool, y migración del checkpointer de sesión a un almacén persistente.

## Capabilities

### New Capabilities
- `wallet-registry`: registro persistente de las verificaciones de wallet, con su estado, la verificación KYC asociada y los datos del titular.

### Modified Capabilities
- `wallet-onboarding`: el requisito "Activación de la wallet" pasa a exigir que la activación se ejecute contra la API KYC mediante una tool, que se registre el resultado de la verificación con cualquier estado y que un fallo de registro no deje la wallet mostrada como activa.

## Impact

- Backend: nueva tool de LangChain para la activación, puerto y adaptador SQLite de persistencia (`sqlite3` de la biblioteca estándar, sin dependencias nuevas de datos), cambios en el puerto `WalletGateway` para devolver `kyc_id` y `status`, y en el nodo de activación del grafo.
- Configuración: variable `WALLET_DB_PATH`; el archivo `.db` se excluye del control de versiones.
- Datos: el archivo SQLite almacena datos personales (DNI, nombre, apellidos, teléfono, email) en claro.
- Contrato externo: `external-api/openapi.yaml` quedó archivado con el change `onboarding-wallet-bajo-monto`; este change lo toma como referencia sin modificarlo.
- Frontend: el componente de onboarding muestra el mensaje final de activación no completada y deja de ofrecer el botón "Activar wallet" cuando el estado del grafo indica que terminó sin activar. El mensaje de wallet activada se sigue mostrando solo si la activación y el registro terminaron bien.
