# Design

## Context

El backend (Python 3.13, hexagonal) tiene un grafo `onboarding` determinista expuesto por AG-UI en `/agent`; no contiene ningún LLM. El frontend tiene un `<copilot-chat agentId="onboarding">` montado pero sin uso: el grafo ignora los mensajes. Ver [proposal.md](./proposal.md) para la motivación y [specs/wallet-assistant/spec.md](./specs/wallet-assistant/spec.md) y [specs/wallet-registry/spec.md](./specs/wallet-registry/spec.md) para los requisitos.

Otro proyecto local del usuario (`../crewai`) ya consume el modelo con el SDK de Copilot mediante `lab_copilot/runtime.py`: `copilot.CopilotClient(use_logged_in_user=True)`, sesión con `model`, `available_tools=[]`, permisos denegados, mensaje de sistema reemplazado y `skip_custom_instructions=True`. Usa `github-copilot-sdk==1.0.28` con Python 3.13.15. El modelo es de solo texto. Este diseño reutiliza ese patrón dentro de un adaptador propio, sin importar código de ese proyecto.

Estado relevante hoy: la tool `activate_wallet` devuelve `kyc_id` solo cuando la wallet se activa; el estado del grafo de onboarding guarda `wallet_id` pero no `kyc_id`; `WalletRepository` solo tiene `save`; `create_app` registra un único agente.

## Goals / Non-Goals

**Goals:**
- Un asistente en el chat que responda con `gpt-6-luna` y que, a petición, muestre los datos registrados de la propia sesión mediante una tool.
- Que los datos registrados nunca lleguen al modelo.
- Mantener el onboarding por formulario intacto y funcional si el modelo falla.

**Non-Goals:**
- Autenticación de usuarios o consultas entre sesiones o tras reiniciar el backend.
- Un modelo que invoque tools por sí mismo (function calling).
- Streaming de tokens, memoria persistente de la conversación y respaldo por palabras clave.
- Credenciales de despliegue distintas a la sesión local de Copilot.

## Decisions

- **Dos agentes, dos grafos:** se añade un grafo `assistant` en un segundo endpoint AG-UI (`/assistant`) y el chat usa `agentId="assistant"`; el formulario sigue con `onboarding`. Mezclar chat libre con un grafo que espera respuestas por `interrupt` es frágil: un mensaje de chat llegaría a un grafo pausado en un paso. Alternativa descartada: un único grafo con rama de chat, por esa razón.
- **Checkpointers separados:** cada grafo compila con su propio `MemorySaver`. El frontend envía el mismo `threadId` a ambos agentes; con un checkpointer compartido los dos grafos escribirían estados de forma distinta bajo el mismo hilo y se corromperían. El asistente no lee el checkpointer del onboarding directamente: lo hace a través de un puerto (siguiente decisión).

  ```
  +-----------+  /agent      +------------------+   MemorySaver A
  | formulario|------------->| grafo onboarding |---> (thread_id: estado, kyc_id)
  +-----------+              +--------+---------+
                                      ^ get_state(thread_id)
  +-----------+  /assistant  +--------+---------+   MemorySaver B
  |   chat    |------------->| grafo assistant  |---> (thread_id: messages)
  +-----------+              +--+----------+----+
                                |          |
                      Copilot (texto)   tool get_my_wallet_data -> SQLite
  ```

- **Puerto `SessionWalletLookup`:** dado un `thread_id` devuelve el `kyc_id` de la wallet de esa sesión o nada. Su adaptador consulta `get_state` del grafo de onboarding. El núcleo y el grafo del asistente no conocen el otro grafo. El estado de onboarding añade `kyc_id` (por defecto `None`, incluido en `initial_state` y en el reinicio por expiración, y completado por el nodo `bootstrap` en hilos existentes).
- **`kyc_id` también para estados no activos:** `WalletNotActivatedError` pasa a llevar `kyc_id` y la tool `activate_wallet` lo devuelve siempre que exista un registro guardado. Así "mis datos" funciona con `PENDING` y `REJECTED`, tal como pide la spec. Si el guardado falla no hay registro y el valor es `None`.
- **Lectura en el registro:** `WalletRepository` añade `find(kyc_id) -> WalletRecord | None`; el adaptador SQLite la implementa con consulta parametrizada y traduce `sqlite3.Error` a `WalletPersistenceError`.
- **El modelo solo genera texto; el grafo ejecuta la tool:** el nodo `classify` envía al modelo la conversación y le pide una respuesta JSON con `intent` (`show_my_data` o `chat`) y `reply`. Con `chat` se muestra `reply`; con `show_my_data` el grafo invoca la tool y descarta `reply`. Una sola llamada al modelo por mensaje. Si la salida no es un JSON válido, se trata como `chat` y se muestra el texto recibido. Alternativas descartadas: function calling del SDK (el patrón local desactiva las tools y el modelo tendría permisos que no se necesitan) y dos llamadas (clasificar y luego responder), por latencia.
- **Tool `get_my_wallet_data`:** `@tool` de `langchain-core` construida con una fábrica que recibe `WalletRepository` y `SessionWalletLookup`. Recibe el `thread_id`, que el nodo toma de la configuración del servidor y no del modelo, y devuelve `{"found": false}` o `{"found": true, "record": {...}}` con los nueve campos sin `kyc_id`. Un prompt manipulado que haga al modelo devolver `show_my_data` solo puede mostrar los datos de la propia sesión.
- **Formato fijo, sin pasar por el modelo:** una función determinista convierte el resultado de la tool en un mensaje con etiquetas en español (una línea por campo) y lo añade como `AIMessage`. El mensaje se marca con `additional_kwargs={"redacted": True}`.
- **Datos fuera del modelo en turnos posteriores:** el estado del asistente conserva los mensajes (con los datos mostrados) para que la UI los vea, pero al construir el prompt se excluyen esos mensajes y se limita el historial a los últimos mensajes. Sin este filtro, el siguiente mensaje enviaría al modelo los datos de la consulta anterior. El mensaje se marca con `additional_kwargs={"redacted": True}`, pero el filtro lo reconoce también por su encabezado fijo (`Estos son tus datos registrados:`): el cliente reenvía la conversación completa en cada turno y `add_messages` reemplaza por identificador el mensaje guardado, así que los metadatos pueden perderse en ese viaje. Una prueba cubre el reenvío sin metadatos.
- **Puerto `ConversationalModel` y adaptador `CopilotChatModel`:** el puerto expone `async complete(messages) -> str` y lanza `ModelUnavailableError` ante fallo o tiempo de espera agotado. El adaptador sigue el patrón de `lab_copilot/runtime.py` (sesión de solo texto, permisos denegados, mensaje de sistema propio, `skip_custom_instructions`). A diferencia de ese código, el cliente es de larga vida: se crea al arrancar la aplicación (`lifespan` de FastAPI) y se cierra al apagarla, y solo se crea una sesión por mensaje. Alternativa descartada: un cliente por mensaje, porque cada uno lanza el runtime de Copilot y añade latencia.
- **Nodos `async`:** el modelo se llama con `await`. No se usa `asyncio.run` dentro del servidor, que falla dentro del bucle de eventos de FastAPI.
- **Autenticación local:** `COPILOT_USE_LOGGED_IN_USER=true` por defecto reutiliza la sesión del CLI de Copilot del usuario de Windows; no hay token en `.env`. Con `false`, el SDK usa el token de las variables de entorno que admite. Variables: `COPILOT_MODEL` (por defecto `gpt-6-luna`), `COPILOT_REASONING_EFFORT`, `COPILOT_TIMEOUT_SECONDS` (por defecto 60).
- **Mensaje de indisponibilidad fijo:** ante `ModelUnavailableError` el nodo responde un mensaje fijo ("El asistente no está disponible por ahora. Puedes continuar con el formulario.") y el grafo termina. No se reintenta.
- **Frontend:** `provideCopilotKit` registra `assistant: new HttpAgent({ url: 'http://localhost:8000/assistant' })` y el `<copilot-chat>` usa `agentId="assistant"` con el mismo `threadId` del formulario. `OnboardingChat` no cambia su lógica.
- **Dependencia fijada:** `github-copilot-sdk==1.0.28`, la versión ya probada en el otro proyecto con la misma versión de Python.

## Risks / Trade-offs

- [El SDK lanza un subproceso del runtime de Copilot; el bucle de eventos por defecto en Windows podría no admitirlo bajo uvicorn] → Se verifica primero, con una llamada real, que el cliente arranca dentro del servidor (tarea 1.2) antes de construir el resto.
- [El texto que el usuario escribe en el chat llega a Copilot, y podría incluir datos personales] → Aceptado; solo se evita reenviarle los datos del registro. Se documenta en el README.
- [Tras reiniciar el backend o abrir otra sesión, el `MemorySaver` pierde el vínculo hilo-wallet y "mis datos" responde que no hay datos] → Limitación aceptada por no existir autenticación; documentada.
- [El modelo devuelve JSON inválido o cambia de intención por un prompt manipulado] → Una salida inválida se trata como respuesta de chat; la tool solo accede a la wallet de la sesión, así que la peor consecuencia es mostrar los datos propios.
- [Latencia de un modelo de razonamiento en un chat] → `COPILOT_REASONING_EFFORT` configurable; el valor por defecto se fija en la tarea 4.1 tras comprobar los valores que acepta el SDK.
- [El plan de Copilot o una política de la organización puede no habilitar `gpt-6-luna`] → El error se trata como indisponibilidad; el modelo es configurable.
- [Si el adaptador AG-UI no emite como mensaje un `AIMessage` añadido por un nodo, el chat no lo mostraría] → Se verifica en la prueba del grafo contra el endpoint y en el navegador (tarea 7.2).

## Migration Plan

1. Añadir `github-copilot-sdk==1.0.28`, instalarlo en el venv y documentar las variables `COPILOT_*` en `backend/README.md` y en `.env`.
2. Asegurar que el CLI de Copilot tiene una sesión iniciada (`copilot` con `/login`) en la máquina del backend.
3. Reiniciar el backend y el frontend.
4. Rollback: quitar el agente `assistant` del frontend y volver a la versión anterior del backend; el onboarding por formulario y la base de datos no se ven afectados.

## Open Questions

- Valores válidos de `COPILOT_REASONING_EFFORT` para `gpt-6-luna`: se comprueban en la tarea 4.1 y no cambian el enfoque.
