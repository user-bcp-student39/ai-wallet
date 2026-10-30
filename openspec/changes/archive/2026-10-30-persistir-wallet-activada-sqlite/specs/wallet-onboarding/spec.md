# Spec Delta

## MODIFIED Requirements

### Requirement: Activación de la wallet
El sistema MUST cambiar el estado de la wallet a activo cuando todos los pasos obligatorios se completan correctamente y la verificación KYC contra la API externa devuelve el estado ACTIVE, y MUST dar acceso al punto de entrada de pagos de bajo monto solo después de registrar el resultado de la verificación.

#### Scenario: Activación exitosa
- **WHEN** el usuario completa el último paso con todos los datos válidos
- **THEN** el sistema cambia el estado de la wallet a activo y muestra el acceso al punto de entrada de pagos de bajo monto

#### Scenario: Sin activación con datos pendientes
- **WHEN** existe al menos un paso obligatorio sin completar
- **THEN** el estado de la wallet permanece sin activar y el punto de entrada de pagos no está disponible

#### Scenario: Verificación KYC con documento TEST derivado
- **WHEN** el usuario confirma la activación con todos los datos válidos
- **THEN** el sistema solicita la verificación KYC con tipo de documento TEST, escenario APPROVED y un documento con prefijo TEST- derivado del DNI sin incluir el DNI real

#### Scenario: Verificación KYC no aprobada
- **WHEN** la API devuelve un estado distinto de ACTIVE
- **THEN** el sistema registra la verificación con ese estado, mantiene la wallet sin activar y muestra que la activación no se completó

#### Scenario: API KYC no disponible
- **WHEN** la API no responde o devuelve un error sin identificador de verificación
- **THEN** el sistema mantiene la wallet sin activar, no registra ninguna verificación y muestra que la activación no se completó

#### Scenario: Fallo al registrar la verificación
- **WHEN** la API responde con cualquier estado pero el registro no puede guardarse
- **THEN** el sistema muestra que la activación no se completó, mantiene la wallet sin activar para el usuario y no da acceso al punto de entrada de pagos
