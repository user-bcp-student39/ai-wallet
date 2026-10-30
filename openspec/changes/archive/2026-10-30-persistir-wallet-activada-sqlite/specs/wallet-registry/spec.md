# Spec Delta

## Purpose

Conserva de forma persistente cada verificación de wallet respondida por la API, con su estado, la verificación KYC asociada y los datos del titular, para poder consultar quién registró su wallet, en qué estado quedó y con qué límite.

## ADDED Requirements

### Requirement: Registro de la verificación de wallet
El sistema MUST guardar un registro persistente por cada verificación KYC que la API responda, con cualquier estado devuelto (ACTIVE, PENDING o REJECTED), y MUST guardar con él los datos del titular y del límite definidos en el onboarding.

#### Scenario: Registro tras activación exitosa
- **WHEN** la API KYC devuelve el estado ACTIVE para un onboarding completo
- **THEN** el sistema guarda un registro con el identificador de verificación KYC, el identificador de wallet, el estado ACTIVE, el DNI, el tipo de documento, nombre, apellidos, teléfono, email y monto máximo

#### Scenario: Registro con estado no activo
- **WHEN** la API KYC devuelve el estado PENDING o REJECTED
- **THEN** el sistema guarda el registro con ese estado y los mismos datos del titular

#### Scenario: Sin registro cuando la API no responde
- **WHEN** la API KYC no responde o devuelve un error sin identificador de verificación
- **THEN** el sistema no guarda ningún registro

### Requirement: Tipo de documento por defecto
El sistema MUST registrar el tipo de documento TEST cuando no se indique otro.

#### Scenario: Tipo de documento predeterminado
- **WHEN** se guarda el registro de una verificación de wallet
- **THEN** el tipo de documento registrado es TEST

### Requirement: Identificador de verificación único
El sistema MUST identificar cada registro por el identificador de verificación KYC y MUST NOT guardar dos registros con el mismo identificador.

#### Scenario: Verificación ya registrada
- **WHEN** se intenta guardar un registro con un identificador de verificación KYC ya existente
- **THEN** el sistema rechaza el guardado y conserva el registro original sin cambios

### Requirement: Ubicación configurable del almacén
El sistema MUST permitir configurar mediante una variable de entorno la ubicación del almacén persistente y MUST crearlo con la estructura necesaria si no existe.

#### Scenario: Almacén inexistente
- **WHEN** el backend arranca y el archivo del almacén no existe en la ubicación configurada
- **THEN** el sistema lo crea con la estructura de registros lista para guardar
