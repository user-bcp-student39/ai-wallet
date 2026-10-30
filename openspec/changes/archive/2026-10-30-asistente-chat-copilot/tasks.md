# Tasks

## 1. Dependencia y arranque del SDK

- [x] 1.1 Declarar `github-copilot-sdk==1.0.28` en `backend/pyproject.toml` e instalarlo en `backend/.venv` con `uv pip install --python .venv\Scripts\python.exe`; verificar que `.venv\Scripts\python.exe -c "import copilot, importlib.metadata as m; print(m.version('github-copilot-sdk'))"` imprime `1.0.28` y que `pytest -q` sigue pasando
- [x] 1.2 Comprobar con una aplicación FastAPI mínima y desechable (fuera del repo) servida con `uvicorn` en Windows que un `CopilotClient` de larga vida arranca dentro del bucle de eventos del servidor y devuelve texto de `gpt-6-luna` con la sesión local de Copilot; verificar que la respuesta llega sin error y, si falla en Windows, detenerse y revisar el diseño antes de seguir

## 2. Lectura en el registro

- [x] 2.1 Añadir `find(kyc_id)` al puerto `WalletRepository` (devuelve `WalletRecord | None`) y a `SqliteWalletRepository` con consulta parametrizada, traduciendo `sqlite3.Error` a `WalletPersistenceError`; actualizar el doble de `conftest.py`; verificar con pruebas: registro existente con todos sus campos, identificador inexistente devuelve `None`, y fallo de lectura lanza `WalletPersistenceError`

## 3. Vínculo entre la sesión y el registro

- [x] 3.1 Hacer que `WalletNotActivatedError` lleve `kyc_id` (el de un registro guardado, si existe), que `OnboardingService.activate` lo informe y que la tool `activate_wallet` lo devuelva siempre que haya registro; con fallo de guardado o API caída debe ser `None`; verificar con pruebas del servicio y de la tool para `ACTIVE`, `PENDING`, `REJECTED`, API caída y fallo de guardado
- [x] 3.2 Añadir `kyc_id` (por defecto `None`) al estado del grafo de onboarding: en `OnboardingState`, `initial_state`, el reinicio por expiración y el nodo `bootstrap` para hilos existentes, y guardarlo en el nodo `activation`; verificar con pruebas del grafo que queda guardado tras `ACTIVE` y `PENDING`, que es `None` tras `REGISTRY_ERROR` y que un estado anterior sin la clave no falla

## 4. Modelo conversacional con Copilot

- [x] 4.1 Definir en `backend/ports/` el puerto `ConversationalModel` (`async complete(messages) -> str`) y `ModelUnavailableError`, e implementar `CopilotChatModel` en `backend/adapters/` con sesión de solo texto (`available_tools=[]`, permisos denegados, mensaje de sistema propio, `skip_custom_instructions`), configurada con `COPILOT_MODEL` (por defecto `gpt-6-luna`), `COPILOT_USE_LOGGED_IN_USER` (por defecto `true`), `COPILOT_REASONING_EFFORT` y `COPILOT_TIMEOUT_SECONDS` (por defecto 60); comprobar en el SDK los valores válidos de `COPILOT_REASONING_EFFORT` y fijar un valor por defecto adecuado para chat; documentar las variables `COPILOT_*` en `backend/README.md`; verificar con pruebas y un cliente falso: valores por defecto de la configuración, construcción del prompt, y que un fallo o un tiempo agotado se convierten en `ModelUnavailableError`
- [x] 4.2 Crear el cliente de Copilot al arrancar la aplicación y cerrarlo al apagarla (`lifespan` de FastAPI), con una sesión por mensaje; verificar con pruebas y una fábrica falsa que se crea una vez al arrancar, se reutiliza entre mensajes y se cierra al apagar

## 5. Consulta de los datos de la sesión

- [x] 5.1 Definir el puerto `SessionWalletLookup` (`thread_id -> kyc_id | None`) en `backend/ports/` y su adaptador, que lee `kyc_id` con `get_state` del grafo de onboarding; verificar con pruebas contra un grafo real y un doble de repositorio: hilo con registro, hilo sin onboarding y hilo desconocido
- [x] 5.2 Crear la tool `get_my_wallet_data` (`@tool` de `langchain-core`) con una fábrica que recibe `WalletRepository` y `SessionWalletLookup`, y la función que formatea el resultado como mensaje en español con una línea por campo; la tool devuelve `{"found": false}` o los nueve campos sin `kyc_id`; verificar con pruebas: nueve campos y ausencia de `kyc_id`, `found` falso sin registro ni sesión, y error de lectura propagado como `WalletPersistenceError`

## 6. Grafo del asistente y endpoint

- [x] 6.1 Implementar el grafo `assistant` en `backend/adapters/` con su propio `MemorySaver`: el nodo `classify` pide al modelo un JSON con `intent` (`show_my_data` o `chat`) y `reply`, trata un JSON inválido como `chat`, invoca la tool con el `thread_id` de la configuración del servidor cuando la intención es `show_my_data`, añade el mensaje formateado marcado `redacted` y excluye esos mensajes y limita el historial al construir el prompt; ante `ModelUnavailableError` responde el mensaje fijo de indisponibilidad; verificar con un modelo falso: respuesta de chat, consulta con registro, consulta sin registro, petición de un DNI ajeno sin mostrar datos ajenos, que el prompt del mensaje siguiente no contiene los valores mostrados, JSON inválido e indisponibilidad del modelo
- [x] 6.2 Registrar el agente `assistant` en un segundo endpoint AG-UI (`/assistant`) dentro de `create_app` y componer el modelo, la tool y el lookup en `backend/server.py`; documentar el endpoint, el alcance por sesión y la limitación tras reiniciar en `backend/README.md`; verificar con pruebas de `create_app` que `/assistant` responde con el texto del asistente a un mensaje, que `/agent` mantiene su comportamiento y que `.venv\Scripts\python.exe -m pytest -q` pasa completo

## 7. Frontend y verificación integrada

- [x] 7.1 Registrar el agente `assistant` (`http://localhost:8000/assistant`) en `provideCopilotKit` y cambiar el `<copilot-chat>` a `agentId="assistant"` con el mismo `threadId`; verificar con `ng build` sin errores
- [x] 7.2 Ejecutar en navegador contra el mock de W1 y con la sesión local de Copilot: una pregunta general recibe respuesta; pedir los datos antes de activar responde que no hay datos registrados; tras activar, pedirlos muestra los nueve campos sin `kyc_id`; pedir los datos de otro DNI no los muestra; un mensaje posterior no se rompe; y con un modelo inválido en `COPILOT_MODEL` el chat avisa que no está disponible mientras el formulario completa el onboarding
