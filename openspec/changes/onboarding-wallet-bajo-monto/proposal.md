# Proposal

## Why

Un usuario móvil (web) que hace transferencias diarias de bajo monto necesita completar el registro de la wallet sin abandonar el proceso. Hoy no existe un flujo de onboarding que guíe los pasos, indique el paso actual ni bloquee datos inválidos con mensajes accionables.

## What Changes

- Nuevo flujo de onboarding conversacional, paso a paso, que muestra la secuencia de pasos y el paso actual en todo momento.
- Datos obligatorios: nombre, apellidos, teléfono, email y DNI.
- Validaciones bloqueantes: no se avanza si falta un dato obligatorio o si es inválido; el mensaje indica cómo corregirlo.
  - DNI: exactamente 8 dígitos numéricos.
  - Monto máximo por operación: definido por el usuario, con 0 < monto <= 500 PEN.
- Moneda por defecto: PEN (soles).
- Interrupción: la sesión de onboarding se mantiene durante un tiempo configurable (5 minutos por defecto). Al expirar, el proceso se reinicia.
- Al finalizar correctamente, el estado de la wallet pasa a activo y el usuario accede al punto de entrada de pagos de bajo monto.

Fuera de alcance: mecanismos de cobro, integración con proveedores de pago y movimiento de dinero.

## Capabilities

### New Capabilities
- `wallet-onboarding`: flujo conversacional de registro y activación de la wallet, incluyendo pasos, validaciones bloqueantes, persistencia temporal de la sesión y cambio de estado a activo.

### Modified Capabilities

## Impact

- Nuevo módulo de onboarding en la aplicación web (interfaz conversacional y validaciones de formulario).
- Almacenamiento temporal del avance del onboarding con tiempo de expiración configurable.
- Modelo de estado de la wallet (pendiente de onboarding / activa).
- Sin cambios en APIs de pagos existentes; el punto de entrada de pagos solo se enlaza al estado activo.
