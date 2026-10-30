# Tasks

## 1. Modelo de onboarding y estado de la wallet

- [ ] 1.1 Definir los pasos del onboarding (datos personales, DNI, monto máximo, activación) y el estado de la wallet (sin activar / activa); verificar con una prueba que el paso inicial es el 1 de 5
- [ ] 1.2 Implementar el almacenamiento del avance con marca de tiempo y tiempo de vida leído de configuración con valor por defecto de 5 minutos; verificar con una prueba que el valor por defecto es 5 minutos y que se puede cambiar por configuración

## 2. Validaciones bloqueantes

- [ ] 2.1 Implementar validación de nombre, apellidos, teléfono, email y DNI como obligatorios; verificar con pruebas que un campo vacío no permite avanzar
- [ ] 2.2 Implementar validación de DNI con exactamente 8 dígitos numéricos; verificar con pruebas "12345678" (válido), "1234567" y "1234567A" (inválidos)
- [ ] 2.3 Implementar validación de monto máximo en PEN con 0 < X <= 500; verificar con pruebas 300 (válido), 0 y 501 (inválidos)
- [ ] 2.4 Aplicar la moneda por defecto PEN en el paso de monto máximo; verificar con una prueba que la moneda mostrada es PEN
- [ ] 2.5 Repetir las validaciones en el servidor antes de persistir cada paso; verificar con una prueba que una petición con DNI inválido es rechazada aunque la interfaz no la envíe

## 3. Flujo conversacional

- [ ] 3.1 Implementar la interfaz conversacional que muestra el paso actual y los pasos restantes; verificar en navegador que el paso 1 de 5 aparece al iniciar
- [ ] 3.2 Mostrar mensajes accionables ante cada error (campo afectado y regla a cumplir) sin avanzar el paso; verificar en navegador con un DNI inválido
- [ ] 3.3 Retomar el flujo en el mismo paso si la sesión no ha expirado, y reiniciar desde el paso 1 si expiró; verificar con una prueba de expiración simulada

## 4. Activación

- [ ] 4.1 Cambiar el estado de la wallet a activo al completar todos los pasos válidos y mostrar el acceso al punto de entrada de pagos de bajo monto; verificar con una prueba de extremo a extremo del flujo completo
- [ ] 4.2 Mantener la wallet sin activar y ocultar el punto de entrada si queda un paso obligatorio pendiente; verificar con una prueba

## 5. Verificación de integración

- [ ] 5.1 Ejecutar el flujo completo de onboarding en navegador móvil y confirmar que la wallet queda activa al final

## Workflow follow-up

- Archivar el cambio después de revisar que todas las tareas están completas.
- Verificar el resultado archivado y sincronizar la spec `wallet-onboarding` con `openspec/specs/`.
