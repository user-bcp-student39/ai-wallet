# Spec Delta

## ADDED Requirements

### Requirement: Recuperación de un registro por verificación
El sistema MUST permitir recuperar un registro persistido a partir de su identificador de verificación KYC, devolviendo todos sus campos, y MUST indicar que no existe cuando ningún registro tenga ese identificador.

#### Scenario: Registro existente
- **WHEN** se solicita el registro de un identificador de verificación guardado
- **THEN** el sistema devuelve el registro completo con los mismos valores que se guardaron

#### Scenario: Registro inexistente
- **WHEN** se solicita un identificador de verificación que no está guardado
- **THEN** el sistema indica que no existe registro y no devuelve ningún dato
