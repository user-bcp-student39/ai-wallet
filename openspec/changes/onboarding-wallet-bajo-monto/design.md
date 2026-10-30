# Design

## Context

El proyecto no tiene código de aplicación ni specs previas; el cambio define el primer comportamiento de la wallet. Stack confirmado: frontend en Angular con CopilotKit y backend en Python con LangGraph, organizado en `backend/` y `frontend/` en la raíz del repositorio. La tool externa es la API `https://bcp-wallet-mock.yefri.workers.dev`; su respuesta actual (`/groups/6?latency=1`) es un estado de salud (`status`, `environment`, `storage`, `startedAt`) y no define endpoints de onboarding, por lo que su contrato real queda pendiente. Ver [proposal.md](./proposal.md) para la motivación y [specs/wallet-onboarding/spec.md](./specs/wallet-onboarding/spec.md) para los requisitos.

## Versiones de tecnologías

Versiones estables más recientes verificadas en los registros oficiales (PyPI, npm y python.org). Se fijan en el proyecto para que la implementación sea reproducible.

| Tecnología | Versión | Motivo |
|---|---|---|
| Node.js | 26.13.0 (LTS) | `engines` de `@angular/cli` 22 exige `^22.22.3 \|\| ^24.15.0 \|\| >=26.0.0` |
| Python | 3.13.18 | Última 3.13 publicada. Se evita 3.14/3.15: `copilotkit` en PyPI exige `<3.15` y LangGraph no declara 3.14 en sus clasificadores |
| langgraph | 1.2.18 | PyPI. `MemorySaver` disponible vía `langgraph-checkpoint` 4.3.1 |
| FastAPI | 0.162.0 | PyPI |
| httpx | 0.28.1 | PyPI |
| pytest | 9.2.0 | PyPI |
| `@angular/core`, `@angular/cli` | 22.2.4, 22.2.5 | npm `latest` |
| TypeScript | 6.0.3 (fijada) | `@angular/compiler-cli` 22 exige `>=6.0 <6.1`; el `latest` de npm (7.0.2) es incompatible |
| rxjs | 7.8.2 | Peer de `@angular/core` 22 y de `@copilotkit/angular` |
| `@copilotkit/angular` | 0.6.0 | npm `latest`; peers `@angular/core` ^22 y `@angular/cdk` ^22 |

`@copilotkit/react-core` (1.83.0) es para React y no aplica a Angular.

## Goals / Non-Goals

**Goals:**
- Flujo conversacional paso a paso con paso actual visible y validaciones bloqueantes.
- Expiración de sesión configurable (5 minutos por defecto).
- Transición del estado de la wallet a activo al completar el onboarding.

**Non-Goals:**
- Mecanismos de cobro, integración con proveedores de pago y movimiento de dinero.
- Verificación de identidad contra fuentes externas (RENIEC u otras).

## Decisions

- **Máquina de estados por pasos:** el onboarding se modela como estados ordenados (datos personales, DNI, monto máximo, activación). Un paso solo avanza si pasa su validación. Alternativa descartada: formulario libre con validación al final, porque incumple la indicación de paso actual y bloqueo inmediato.
- **Backend hexagonal (Python):** `domain/` contiene las reglas de validación y la máquina de estados; `application/` contiene los casos de uso; `ports/` define `WalletGateway`; `adapters/` tiene un adaptador de entrada (endpoint que expone el agente a CopilotKit) y uno de salida (cliente HTTP a la API mock). El dominio no importa FastAPI, LangGraph ni httpx.
- **LangGraph en el backend:** el workflow de onboarding es un grafo donde cada paso es un nodo y un paso con validación fallida vuelve al mismo nodo mediante una arista condicional. Alternativa descartada: LangGraph en el navegador, porque el runtime de agentes no corre de forma fiable allí.
- **Frontend Angular con CopilotKit:** componentes standalone, signals, estrategia `OnPush`, formularios reactivos con validadores y rutas con carga diferida. La interfaz consume el agente mediante CopilotKit y no llama directamente a la API externa.
- **Adaptador de la tool:** la URL base se configura por variable de entorno. Si el contrato real difiere del mock, solo cambia el adaptador; el dominio y el agente no se tocan.
- **Validación en el servidor además de la interfaz:** la interfaz muestra el mensaje de corrección al instante, pero el servidor vuelve a validar cada paso antes de persistirlo. Así una petición manipulada no puede saltarse una regla.
- **Expiración de sesión en el servidor:** el avance se guarda con una marca de tiempo y un tiempo de vida leído de configuración (`5 min` por defecto). Alternativa descartada: expirar solo en el cliente, porque puede manipularse.
- **Estado de sesión con `MemorySaver` de LangGraph:** el grafo compila con `MemorySaver` como checkpointer. Cada sesión usa un `thread_id` (UUID v4) generado por el frontend y enviado en `config["configurable"]["thread_id"]` en cada invocación. El estado contiene los datos del onboarding, el paso actual y la marca de tiempo del último avance; el TTL se comprueba al entrar en cada nodo. El frontend guarda el `thread_id` en `sessionStorage` para recuperarlo tras recargar la pantalla. Alternativa descartada: `localStorage`, porque la sesión debe terminar con la pestaña.
- **Configuración del tiempo de sesión:** valor en configuración del proyecto, no hardcodeado, para que cambie sin tocar código.
- **Monto máximo como límite configurable del usuario:** el usuario elige un valor en (0, 500] PEN. El tope de 500 es una constante de negocio, no un valor configurable por usuario.

## Risks / Trade-offs

- [Pérdida de datos al expirar la sesión] → Mensaje claro antes de expirar y reinicio explícito, para que el usuario sepa que debe volver a ingresar sus datos.
- [Validación de formato del DNI no equivale a identidad real] → Aceptado para el mínimo viable; la verificación de identidad queda fuera de alcance.
- [Reglas de formato de teléfono y email aún no definidas en detalle] → Ver preguntas abiertas.
- [Contrato de la tool desconocido: la API mock solo expone un estado de salud] → Puerto `WalletGateway` con adaptador aislado; el resto del sistema no depende del contrato real.
- [`MemorySaver` se pierde al reiniciar el backend] → Un `thread_id` no encontrado se trata como sesión expirada: el flujo vuelve al paso 1. Un checkpointer persistente queda fuera de este alcance.
- [LangGraph y CopilotKit requieren una conexión de agente entre backend y frontend] → Endpoint de agente con prueba de conexión antes de construir la interfaz.

## Migration Plan

No aplica: el sistema no tiene datos previos. Rollback: desactivar la ruta de onboarding y dejar la wallet en estado sin activar.

## Open Questions

- Formato exacto aceptado para teléfono (prefijo, longitud) y para email (dominios permitidos o solo formato estándar). Pueden definirse en la fase de tareas sin cambiar los requisitos actuales.
- Endpoints y contrato reales de la tool de onboarding en la API externa. Mientras no existan, el adaptador se implementa contra el puerto y con respuestas simuladas.
- Resuelta: el avance de sesión vive en el backend, en el estado de LangGraph con `MemorySaver`, y el frontend solo guarda el `thread_id` (ver Decisions).
