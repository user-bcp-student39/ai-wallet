# wallet-onboarding Specification

## Purpose

Permite a un usuario móvil (web) completar el registro de su wallet mediante un flujo conversacional guiado, con validaciones bloqueantes y activación para pagos de bajo monto.

## Requirements

### Requirement: Secuencia de pasos visible
El sistema MUST mostrar la secuencia completa de pasos del onboarding y MUST indicar el paso actual en todo momento durante el flujo.

#### Scenario: Muestra el paso actual
- **WHEN** el usuario inicia el onboarding
- **THEN** el sistema muestra el paso 1 de 5 como paso actual y la lista de pasos restantes

#### Scenario: Actualiza el paso al avanzar
- **WHEN** el usuario completa un paso válido
- **THEN** el sistema muestra el siguiente paso como paso actual y marca el anterior como completado

### Requirement: Datos obligatorios
El sistema MUST solicitar como obligatorios los datos nombre, apellidos, teléfono, email y DNI, y MUST NOT permitir avanzar mientras alguno esté vacío.

#### Scenario: Bloquea paso con dato vacío
- **WHEN** el usuario envía un paso con el campo nombre vacío
- **THEN** el sistema no avanza y muestra un mensaje indicando que el nombre es obligatorio

### Requirement: Validación de DNI
El sistema MUST aceptar como DNI únicamente exactamente 8 dígitos numéricos y MUST bloquear el avance en cualquier otro caso.

#### Scenario: DNI válido
- **WHEN** el usuario ingresa "12345678"
- **THEN** el sistema acepta el dato y avanza al siguiente paso

#### Scenario: DNI inválido
- **WHEN** el usuario ingresa "1234567" o "1234567A"
- **THEN** el sistema no avanza y muestra un mensaje indicando que el DNI debe tener exactamente 8 dígitos numéricos

### Requirement: Monto máximo por operación
El sistema MUST permitir al usuario definir un monto máximo por operación en PEN, MUST aceptar valores mayores que 0 y menores o iguales a 500, y MUST bloquear el avance en cualquier otro caso.

#### Scenario: Monto dentro del rango
- **WHEN** el usuario define un monto máximo de 300
- **THEN** el sistema guarda 300 PEN como monto máximo por operación y avanza

#### Scenario: Monto fuera del rango
- **WHEN** el usuario define un monto máximo de 501
- **THEN** el sistema no avanza y muestra un mensaje indicando que el monto debe ser mayor que 0 y no superar 500 PEN

### Requirement: Moneda por defecto
El sistema MUST usar PEN (soles) como moneda por defecto en el onboarding.

#### Scenario: Moneda predeterminada
- **WHEN** el usuario llega al paso de monto máximo
- **THEN** el sistema muestra la moneda como PEN sin requerir selección

### Requirement: Mensajes accionables
El sistema MUST mostrar, ante cada dato inválido o faltante, un mensaje que indique qué corregir.

#### Scenario: Mensaje de corrección
- **WHEN** el usuario envía un dato inválido
- **THEN** el sistema muestra el campo afectado y la regla que debe cumplir, y mantiene el paso actual

### Requirement: Sesión de onboarding con expiración configurable
El sistema MUST mantener el avance del onboarding durante un tiempo configurable, con 5 minutos por defecto, y MUST reiniciar el proceso cuando la sesión expire.

#### Scenario: Retoma dentro del plazo
- **WHEN** el usuario regresa al onboarding antes de que expire la sesión
- **THEN** el sistema retoma el flujo en el mismo paso donde se quedó

#### Scenario: Reinicio tras expiración
- **WHEN** el usuario regresa al onboarding después de que expire la sesión
- **THEN** el sistema reinicia el onboarding desde el paso 1

### Requirement: Activación de la wallet
El sistema MUST cambiar el estado de la wallet a activo cuando todos los pasos obligatorios se completan correctamente, y MUST dar acceso al punto de entrada de pagos de bajo monto.

#### Scenario: Activación exitosa
- **WHEN** el usuario completa el último paso con todos los datos válidos
- **THEN** el sistema cambia el estado de la wallet a activo y muestra el acceso al punto de entrada de pagos de bajo monto

#### Scenario: Sin activación con datos pendientes
- **WHEN** existe al menos un paso obligatorio sin completar
- **THEN** el estado de la wallet permanece sin activar y el punto de entrada de pagos no está disponible
