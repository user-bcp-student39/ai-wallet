# Design

## Context

El onboarding ya activa la wallet: el nodo `activation` del grafo llama a `OnboardingService.activate`, que usa el puerto `WalletGateway`, implementado por `WalletApiClient` contra `POST /kyc/verifications` (contrato W1 en [openapi.yaml](../archive/2026-10-30-onboarding-wallet-bajo-monto/external-api/openapi.yaml), archivado con el change anterior). Hoy `WalletActivation` solo devuelve `wallet_id`; el `id` de verificación y el `status` se descartan, y no existe ningún almacén persistente (solo `MemorySaver`). Ver [proposal.md](./proposal.md) para la motivación y [specs/wallet-registry/spec.md](./specs/wallet-registry/spec.md) y [specs/wallet-onboarding/spec.md](./specs/wallet-onboarding/spec.md) para los requisitos.

Restricciones heredadas: arquitectura hexagonal (el dominio y la aplicación no importan LangChain, `httpx` ni `sqlite3`), versiones fijadas en `pyproject.toml`, variables de entorno cargadas desde `backend/.env`, y documento enviado como `TEST-<HMAC(DNI)>` (el DNI real no sale hacia la API).

## Goals / Non-Goals

**Goals:**
- Registrar en SQLite cada verificación que la API responde, con el estado devuelto, con los campos de la spec y de forma coherente con el resultado de la activación.
- Invocar la activación desde el grafo mediante una tool de LangChain.
- Mantener el núcleo (dominio y aplicación) libre de dependencias de infraestructura.

**Non-Goals:**
- Cifrado en reposo, retención o anonimización de los datos personales.
- Idempotencia ante altas repetidas con el mismo DNI.
- Un LLM que decida cuándo invocar la tool: el grafo la invoca de forma determinista.
- Migrar el `MemorySaver` de sesión a un checkpointer persistente.

## Decisions

- **La tool envuelve el caso de uso, no el cliente HTTP:** se añade en `adapters/` una tool `activate_wallet` (`@tool` de `langchain-core`) construida con una fábrica que recibe el `OnboardingService` ya compuesto. La tool recibe los datos del onboarding, ejecuta `OnboardingService.activate` y devuelve un resultado serializable (`activated`, `wallet_id`, `kyc_id`, `reason`). El nodo `activation` la invoca con `tool.invoke(...)`. Así la llamada a la API y el guardado quedan en un solo punto y el grafo no conoce `WalletGateway` ni el repositorio. Alternativa descartada: dejar el nodo llamando al servicio directamente, porque no cumple la petición de invocar la API mediante una tool.
- **Sin LLM ni `ToolNode`:** la tool se invoca directamente desde el nodo. `ToolNode` y `bind_tools` solo aportan cuando un modelo emite la llamada, y el flujo es determinista.
- **La persistencia vive en el caso de uso, detrás de un puerto:** nuevo puerto `WalletRepository` (`save(record)`) en `ports/`. `OnboardingService.activate` llama a `gateway.activate_wallet`, y siempre que el resultado traiga `kyc_id` (cualquier `status`) construye el registro y llama a `repository.save`; solo después decide si la wallet queda activa (`ACTIVE`) o no. Sin `kyc_id` (API caída o error sin cuerpo) no hay registro. Alternativa descartada: guardar desde el nodo del grafo, porque mezclaría persistencia con orquestación y sería más difícil de probar.
- **`WalletActivation` pasa a exponer `kyc_id` y `status`:** `WalletApiClient` los lee de la respuesta (`id`, `wallet_id`, `status`) también cuando el estado no es `ACTIVE`, y los deja vacíos si no hay cuerpo válido. `activated` sigue siendo verdadero solo con `status == ACTIVE`.
- **Adaptador SQLite con `sqlite3` de la biblioteca estándar:** una clase `SqliteWalletRepository` que crea la tabla si no existe (`CREATE TABLE IF NOT EXISTS`) al construirse y guarda con consultas parametrizadas. No se añade ORM ni dependencia de datos. Alternativa descartada: SQLAlchemy, por exceso para una sola tabla.
- **Esquema de la tabla `wallets`:**

  | Columna | Tipo | Nota |
  |---|---|---|
  | `kyc_id` | TEXT | Clave primaria; `id` de `POST /kyc/verifications` |
  | `wallet_id` | TEXT NOT NULL | `wallet_id` de la respuesta |
  | `state` | TEXT NOT NULL | Estado devuelto por la API: `ACTIVE`, `PENDING` o `REJECTED` |
  | `document_number` | TEXT NOT NULL | DNI real |
  | `document_type` | TEXT NOT NULL | Por defecto `TEST` |
  | `name` | TEXT NOT NULL | Nombre |
  | `last_name` | TEXT NOT NULL | Apellidos |
  | `phone` | TEXT NOT NULL | Teléfono |
  | `email` | TEXT NOT NULL | Correo |
  | `max_amount` | TEXT NOT NULL | Monto máximo como texto decimal, para no perder precisión con `Decimal` |

  La columna se llama `wallet_id` (no `walled_id`): se interpreta como errata de la petición original. No se añade `UNIQUE` sobre `document_number`: un mismo DNI puede activar otra wallet, coherente con que la API no evita altas repetidas.
- **Conexión por operación:** el repositorio abre una conexión por llamada a `save`. El grafo se ejecuta en hilos distintos del servidor y `sqlite3` no permite compartir una conexión entre hilos por defecto. Con el volumen esperado, abrir una conexión por guardado es suficiente.
- **Ruta configurable:** `WALLET_DB_PATH` en `backend/.env`, con valor por defecto `wallet.db` relativo a `backend/`. `server.py` la lee y compone el repositorio. Se añade `*.db` al `.gitignore` de `backend/`.
- **Fallo de persistencia = activación fallida:** si `save` lanza, con cualquier estado, el servicio levanta `WalletPersistenceError`; el nodo responde con `activated: False` y `reason: "REGISTRY_ERROR"`. Cuando el estado no es `ACTIVE` y el guardado va bien, el nodo responde `activated: False` con el estado devuelto como motivo. La UI muestra el mensaje de activación no completada (ver la decisión siguiente) cuando `activated` es falso al terminar, y el acceso a pagos depende de `activated`. No hay reintento automático: repetir la llamada crearía otra wallet en la API.
- **Mensaje final en la UI, sin reintento:** el componente de onboarding deriva `failed` del estado del grafo (`done` verdadero y `activated` falso) y muestra un mensaje de error (`role="alert"`) sin detalles técnicos, ocultando el botón "Activar wallet". Hasta ahora el componente solo distinguía "activada" y volvía a mostrar el botón del paso 5, sin mensaje. No se ofrece reintento ni reinicio: en ese hilo el grafo ya terminó y un reintento de un fallo de guardado crearía otra wallet. Como el estado `done`/`activated` viaja en la instantánea del hilo, el mensaje también se muestra tras recargar la página. Alternativa descartada: botón "Empezar de nuevo" con un hilo nuevo, por añadir un flujo de reinicio fuera del alcance.
- **Documento hacia la API sin cambios:** se mantiene `TEST-<HMAC(DNI)>`; solo se guarda el DNI real en SQLite. Alternativa descartada: enviar `TEST-<DNI>`, porque el DNI viajaría en claro a un tercero y el contrato indica no enviar documentos reales.
- **`langchain-core` como dependencia directa:** ya está instalada como dependencia transitiva de `langgraph` (1.7.3). Se declara en `pyproject.toml` con versión fija para no depender de una transitiva.

## Risks / Trade-offs

- [La API crea la wallet pero el guardado local falla: queda una wallet huérfana en la API y el usuario ve error] → Se informa error sin reintento automático y se registra el `kyc_id` en el log del servidor (sin datos personales) para reconciliación manual. La reconciliación automática queda fuera de alcance.
- [Datos personales en claro en el archivo SQLite] → Aceptado en este alcance; el archivo está fuera de git y su ubicación es configurable. Cifrado y retención quedan como trabajo futuro.
- [Dos activaciones con el mismo DNI crean dos wallets en la API y dos registros] → La clave primaria es el `kyc_id`, que difiere entre verificaciones; no se bloquea por DNI.
- [`sqlite3` con varias peticiones concurrentes puede devolver `database is locked`] → Una conexión por operación con tiempo de espera (`timeout`) mayor al valor por defecto; el error se trata como fallo de persistencia.
- [La tool añade una capa sin LLM] → Se asume por indicación explícita; la tool es un envoltorio delgado, por lo que quitarla o cambiarla por una invocada por un modelo no altera el caso de uso.

## Migration Plan

1. Añadir `langchain-core` a `pyproject.toml` y `WALLET_DB_PATH` a `backend/.env` y a `backend/README.md`.
2. Desplegar el backend: la tabla se crea sola al arrancar. No hay datos previos que migrar.
3. Rollback: volver a la versión anterior del backend; el archivo `.db` puede borrarse sin afectar al flujo de onboarding.
