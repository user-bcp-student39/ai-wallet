# Frontend

Chat de onboarding de wallet en Angular, conectado al agente del backend (LangGraph vía AG-UI), con un tablero de trazabilidad del flujo.

## Estructura

- `src/app/chat/`: panel del chat (pasos, burbujas, respuestas rápidas y composer).
- `src/app/core/`: lógica sin UI.
  - `onboarding-agent.ts`: conversación con el agente; pregunta campo a campo y reanuda cada interrupt con las respuestas del paso.
  - `onboarding-transport.ts`: URL del agente (`ONBOARDING_URL`) y fábrica del cliente AG-UI (`AGENT_FACTORY`).
  - `onboarding.model.ts`: pasos, campos y tipos del prompt/estado del grafo.
  - `trace-store.ts` y `trace.model.ts`: trazas y analítica de la sesión.
- `src/app/dashboard/`: tablero con la traza de eventos AG-UI (ejecuciones, nodos del grafo, interrupts, estado y analítica).

## Configuración

La URL del agente (`onboardingUrl`) está en `src/environments/environment.ts` y apunta por defecto a `http://localhost:8000/agent`. El backend debe estar levantado (ver `backend/README.md`).

El `threadId` se guarda en `sessionStorage`: al recargar la página se retoma el registro en el paso pendiente. «Salir de sesión» abre un thread nuevo.

## Comandos

```bash
npm install
npm start          # http://localhost:4200
npm run build
npm test
```
