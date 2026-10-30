# Proposal

## Why

El chat de la pantalla de onboarding está montado pero no hace nada: el agente `onboarding` solo avanza por el formulario e ignora los mensajes. El usuario no puede preguntar dudas sobre el proceso ni consultar los datos que ya registró, y hay una suscripción de Copilot disponible con el modelo `gpt-6-luna` que no se aprovecha.

## What Changes

- Un asistente conversacional responde en el chat usando el LLM de Copilot (`gpt-6-luna`, configurable). Responde dudas sobre el onboarding y sobre la wallet de bajo monto.
- Si el usuario pregunta por sus datos registrados, una tool obtiene el registro de la wallet de la sesión actual y la interfaz muestra todos los campos excepto el identificador de verificación (`kyc_id`): `wallet_id`, estado, DNI, tipo de documento, nombre, apellidos, teléfono, email y monto máximo.
- La tool resuelve la wallet en el servidor a partir de la sesión (hilo). El modelo nunca proporciona identificadores: un DNI u otro dato escrito en el chat no sirve para consultar datos de otra persona.
- Los datos registrados se muestran con un formato fijo generado por la aplicación y no se envían al modelo, ni en la consulta ni en los mensajes siguientes de la conversación.
- El modelo solo genera texto: no ejecuta herramientas ni tiene permisos sobre archivos o comandos. El modelo clasifica la intención del mensaje y el grafo decide si invoca la tool.
- Si Copilot no está disponible, el chat lo indica y el formulario de onboarding sigue funcionando sin cambios.
- El agente de onboarding guarda en el estado del hilo el identificador de verificación de su registro, para que el asistente pueda enlazar la sesión con la wallet. Esto incluye registros con estado no activo.
- El frontend registra un segundo agente (`assistant`) y el chat pasa a usarlo; el formulario sigue usando `onboarding`.

Fuera de alcance: autenticación de usuarios, consultas de datos después de reiniciar el backend o desde otra sesión, un LLM que invoque tools por sí mismo, respaldo de la clasificación de intención por palabras clave cuando el modelo falla, streaming de tokens, memoria persistente de la conversación, y desplegar con una credencial distinta a la sesión local de Copilot.

## Capabilities

### New Capabilities
- `wallet-assistant`: asistente conversacional del chat con LLM, consulta de los datos registrados de la propia wallet con alcance limitado a la sesión, protección de esos datos frente al modelo y comportamiento ante indisponibilidad del modelo.

### Modified Capabilities
- `wallet-registry`: se añade el requisito de recuperar un registro persistido por su identificador de verificación.

## Impact

- Backend: dependencia `github-copilot-sdk` (fijada a la versión ya usada en otro proyecto local), puertos y adaptadores para el modelo conversacional y para resolver la wallet de la sesión, nueva tool de consulta, segundo grafo y segundo endpoint AG-UI, lectura en `WalletRepository` y su adaptador SQLite, y el estado del grafo de onboarding con el identificador de verificación.
- Configuración: variables `COPILOT_MODEL` (por defecto `gpt-6-luna`), `COPILOT_USE_LOGGED_IN_USER`, `COPILOT_REASONING_EFFORT` y un tiempo máximo de espera; documentadas en `backend/README.md`. Sin secretos en el repositorio.
- Frontend: configuración de `provideCopilotKit` con el agente `assistant` y cambio del `agentId` del `<copilot-chat>`.
- Datos personales: el texto que el usuario escribe en el chat sí llega a Copilot; solo se evita reenviarle los datos del registro.
- Operación: requiere que el CLI de Copilot tenga una sesión iniciada en la máquina donde corre el backend.
