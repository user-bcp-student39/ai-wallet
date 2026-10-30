# Tasks

## 1. Dependencias y configuración

- [x] 1.1 Declarar `langchain-core==1.7.3` en `backend/pyproject.toml` y añadir `*.db` a `backend/.gitignore`; verificar que `.venv\Scripts\python.exe -c "import langchain_core"` funciona y que `git check-ignore backend/wallet.db` lo reporta como ignorado

## 2. Puerto y caso de uso

- [x] 2.1 Ampliar `WalletActivation` en `backend/ports/wallet_gateway.py` con `kyc_id` y `status`, y adaptar `WalletApiClient` para leerlos de la respuesta (`id`, `wallet_id`, `status`) con cualquier estado; mantener `activated` verdadero solo con `ACTIVE` y dejar `kyc_id` vacío si no hay cuerpo válido; verificar con pruebas de `test_wallet_api_client.py` que se devuelven los tres campos con `ACTIVE`, `PENDING` y `REJECTED`, y que un error sin cuerpo o una API caída no devuelven `kyc_id`
- [x] 2.2 Definir en `backend/ports/` el puerto `WalletRepository` (`save`) y el registro `WalletRecord` con los campos de la spec, y `WalletPersistenceError` en la aplicación; verificar con una prueba que un repositorio en memoria satisface el puerto
- [x] 2.3 Hacer que `OnboardingService.activate` guarde el registro siempre que la API devuelva un `kyc_id` (con `document_type` `TEST`, `state` igual al `status` devuelto y `max_amount` como texto decimal), no guarde nada sin `kyc_id`, y lance `WalletPersistenceError` si el guardado falla, sin importar `sqlite3` ni LangChain; verificar con pruebas del servicio: registro con `ACTIVE`, `PENDING` y `REJECTED` (solo `ACTIVE` activa), sin registro con API caída, y error de persistencia propagado en cualquier estado

## 3. Adaptador SQLite

- [x] 3.1 Implementar `SqliteWalletRepository` en `backend/adapters/` con `sqlite3`: crea la tabla `wallets` con `kyc_id` como clave primaria si no existe, abre una conexión por guardado con `timeout` ampliado y usa consultas parametrizadas; traducir cualquier `sqlite3.Error` a `WalletPersistenceError`; verificar con pruebas sobre un archivo temporal: creación de la tabla, guardado de todos los campos, rechazo de un `kyc_id` duplicado sin alterar el registro original, y error de persistencia ante una ruta no escribible
- [x] 3.2 Leer `WALLET_DB_PATH` (por defecto `wallet.db` junto a `backend/`) y componer el repositorio en `backend/server.py`, pasándolo a `create_app`; verificar con una prueba de `create_app` que el repositorio se inyecta y arrancando el servidor que el archivo `.db` se crea con la tabla `wallets`

## 4. Tool de LangChain y grafo

- [x] 4.1 Crear en `backend/adapters/` la fábrica de la tool `activate_wallet` (`@tool` de `langchain-core`) que ejecuta `OnboardingService.activate` y devuelve `activated`, `wallet_id`, `kyc_id` y `reason`; verificar con pruebas que la tool devuelve el resultado esperado con un doble de gateway y repositorio
- [x] 4.2 Hacer que el nodo `activation` de `langgraph_onboarding.py` invoque la tool en lugar de llamar al servicio, y que ante `WalletPersistenceError` termine con `activated: False` y `reason: "REGISTRY_ERROR"`; registrar en el log el `kyc_id` sin datos personales; verificar con pruebas del grafo: activación con registro guardado, no aprobada (`PENDING`/`REJECTED`) con registro guardado y sin activar, API caída sin registro, y fallo de guardado sin activar
- [x] 4.3 Actualizar los dobles de `backend/tests/conftest.py` y los asserts existentes al nuevo `WalletActivation`, y la referencia a `openapi.yaml` en el docstring de `wallet_api_client.py` a su ruta archivada; verificar con `.venv\Scripts\python.exe -m pytest -q` que toda la suite pasa

## 5. Documentación y verificación integrada

- [x] 5.1 Documentar `WALLET_DB_PATH` y el archivo SQLite en `backend/README.md` y en la tabla de variables; verificar que el README lista la variable, su valor por defecto y que el `.db` no se versiona
- [x] 5.2 Ejecutar el flujo completo en navegador contra el mock de W1 y confirmar que se guarda un registro en `wallets` con `kyc_id`, `wallet_id`, `state` `ACTIVE`, DNI, tipo `TEST`, nombre, apellidos, teléfono, email y monto máximo; verificar consultando la tabla con `sqlite3` desde Python
- [x] 5.3 Mostrar en `frontend/src/app/onboarding/` un mensaje final (`role="alert"`) de que la activación no se completó cuando el estado del grafo indica `done` verdadero y `activated` falso, y ocultar el botón "Activar wallet" en ese caso; verificar con `ng build` sin errores y con una prueba del componente, si el proyecto ya tiene infraestructura de pruebas del frontend, o en el navegador en la tarea 5.4
- [x] 5.4 Provocar un fallo de guardado (ruta no escribible) y confirmar en navegador que la UI muestra que la activación no se completó, no ofrece "Activar wallet" y no habilita el acceso a pagos, también tras recargar la página; verificar que no queda ningún registro nuevo
