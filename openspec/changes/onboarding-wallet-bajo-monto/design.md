# Design

## Context

El proyecto no tiene código de aplicación ni specs previas; el cambio define el primer comportamiento de la wallet. La interfaz será web en dispositivo móvil y el onboarding será conversacional. Ver [proposal.md](./proposal.md) para la motivación y [specs/wallet-onboarding/spec.md](./specs/wallet-onboarding/spec.md) para los requisitos.

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
- **Validación en el servidor además de la interfaz:** la interfaz muestra el mensaje de corrección al instante, pero el servidor vuelve a validar cada paso antes de persistirlo. Así una petición manipulada no puede saltarse una regla.
- **Expiración de sesión en el servidor:** el avance se guarda con una marca de tiempo y un tiempo de vida leído de configuración (`5 min` por defecto). Alternativa descartada: expirar solo en el cliente, porque puede manipularse.
- **Configuración del tiempo de sesión:** valor en configuración del proyecto, no hardcodeado, para que cambie sin tocar código.
- **Monto máximo como límite configurable del usuario:** el usuario elige un valor en (0, 500] PEN. El tope de 500 es una constante de negocio, no un valor configurable por usuario.

## Risks / Trade-offs

- [Pérdida de datos al expirar la sesión] → Mensaje claro antes de expirar y reinicio explícito, para que el usuario sepa que debe volver a ingresar sus datos.
- [Validación de formato del DNI no equivale a identidad real] → Aceptado para el mínimo viable; la verificación de identidad queda fuera de alcance.
- [Reglas de formato de teléfono y email aún no definidas en detalle] → Ver preguntas abiertas.

## Migration Plan

No aplica: el sistema no tiene datos previos. Rollback: desactivar la ruta de onboarding y dejar la wallet en estado sin activar.

## Open Questions

- Formato exacto aceptado para teléfono (prefijo, longitud) y para email (dominios permitidos o solo formato estándar). Pueden definirse en la fase de tareas sin cambiar los requisitos actuales.
