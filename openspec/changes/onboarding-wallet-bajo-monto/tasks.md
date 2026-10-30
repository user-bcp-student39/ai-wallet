# Tasks

## 1. Estructura y entorno

- [ ] 1.1 Crear las carpetas `backend/` y `frontend/` en la raíz del repositorio; verificar que ambas existen y que el código de la aplicación está solo dentro de ellas
- [ ] 1.2 Crear el proyecto Python en `backend/` con Python 3.13.18, langgraph 1.2.18, FastAPI 0.162.0, httpx 0.28.1 y pytest 9.2.0; verificar con `pytest` que el proyecto arranca sin errores
- [ ] 1.3 Crear el proyecto Angular en `frontend/` con Node.js 26.13.0, Angular 22.2.x, TypeScript 6.0.3 (fijada, no 7.x), rxjs 7.8.2 y `@copilotkit/angular` 0.6.0; verificar con `ng build` que compila sin errores

## 2. Backend hexagonal: núcleo y puertos

- [ ] 2.1 Implementar en `backend/domain/` la máquina de estados del onboarding y en `backend/application/` los casos de uso, sin dependencias de framework; verificar con pruebas unitarias que no importan FastAPI, LangGraph ni httpx
- [ ] 2.2 Definir el puerto `WalletGateway` en `backend/ports/`; verificar con una prueba que un doble en memoria lo satisface

## 3. Adaptadores y agente LangGraph

- [ ] 3.1 Implementar en `backend/adapters/` el cliente de salida hacia la API configurable por variable de entorno, según el contrato de [external-api/openapi.yaml](./external-api/openapi.yaml); verificar con `curl https://bcp-wallet-mock.yefri.workers.dev/groups/6?latency=1` y con una prueba que simula la respuesta
- [ ] 3.2 Implementar el workflow LangGraph con un nodo por paso, aristas condicionales que vuelven al paso con error y compilación con `MemorySaver`; cada invocación usa `config["configurable"]["thread_id"]`; verificar con pruebas del grafo para un flujo válido, otro con DNI inválido y otro con un `thread_id` nuevo
- [ ] 3.3 Exponer el agente mediante un endpoint compatible con CopilotKit; verificar que el frontend recibe una respuesta del agente

## 4. Modelo de onboarding y estado de la wallet

- [ ] 4.1 Definir los pasos del onboarding (datos personales, DNI, monto máximo, activación) y el estado de la wallet (sin activar / activa); verificar con una prueba que el paso inicial es el 1 de 5
- [ ] 4.2 Guardar el avance, los datos del onboarding y la marca de tiempo en el estado del grafo (`MemorySaver`, indexado por `thread_id`); comprobar el TTL configurable (5 minutos por defecto) al entrar en cada nodo; verificar con una prueba del valor por defecto, del cambio por configuración y de reinicio al expirar

## 5. Validaciones bloqueantes

- [ ] 5.1 Implementar validación de nombre, apellidos, teléfono, email y DNI como obligatorios; verificar con pruebas que un campo vacío no permite avanzar
- [ ] 5.2 Implementar validación de DNI con exactamente 8 dígitos numéricos; verificar con pruebas "12345678" (válido), "1234567" y "1234567A" (inválidos)
- [ ] 5.3 Implementar validación de monto máximo en PEN con 0 < X <= 500; verificar con pruebas 300 (válido), 0 y 501 (inválidos)
- [ ] 5.4 Aplicar la moneda por defecto PEN en el paso de monto máximo; verificar con una prueba que la moneda mostrada es PEN
- [ ] 5.5 Repetir las validaciones en el servidor antes de persistir cada paso; verificar con una prueba que una petición con DNI inválido es rechazada aunque la interfaz no la envíe

## 6. Flujo conversacional en Angular

- [ ] 6.1 Implementar en `frontend/` la interfaz conversacional con CopilotKit que muestra el paso actual y los pasos restantes; verificar en navegador que el paso 1 de 5 aparece al iniciar conversacional que muestra el paso actual y los pasos restantes; verificar en navegador que el paso 1 de 5 aparece al iniciar
- [ ] 6.2 Mostrar mensajes accionables ante cada error (campo afectado y regla a cumplir) sin avanzar el paso; verificar en navegador con un DNI inválido
- [ ] 6.3 Generar el `thread_id` (UUID v4) en el frontend, guardarlo en `sessionStorage` y reutilizarlo tras recargar la pantalla; si el backend indica que el hilo no existe o expiró, crear uno nuevo y empezar en el paso 1; verificar en navegador recargando la pantalla en el paso 2 y comprobando que el flujo continúa

## 7. Activación

- [ ] 7.1 Cambiar el estado de la wallet a activo al completar todos los pasos válidos y mostrar el acceso al punto de entrada de pagos de bajo monto; verificar con una prueba de extremo a extremo del flujo completo
- [ ] 7.2 Mantener la wallet sin activar y ocultar el punto de entrada si queda un paso obligatorio pendiente; verificar con una prueba

## 8. Verificación de integración

- [ ] 8.1 Ejecutar el flujo completo de onboarding en navegador móvil y confirmar que la wallet queda activa al final

## Workflow follow-up

- Archivar el cambio después de revisar que todas las tareas están completas.
- Verificar el resultado archivado y sincronizar la spec `wallet-onboarding` con `openspec/specs/`.
