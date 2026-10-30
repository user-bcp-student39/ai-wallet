# wallet-assistant Specification

## Purpose

Atiende en el chat las dudas del usuario sobre el onboarding de su wallet y le muestra los datos que registró, con alcance limitado a su propia sesión y sin exponer esos datos al modelo de lenguaje.

## Requirements

### Requirement: Respuesta conversacional en el chat
El sistema MUST responder en el chat a los mensajes del usuario con un modelo de lenguaje, orientando sus respuestas al onboarding y a la wallet de bajo monto, y MUST mantener operativo el formulario de onboarding mientras tanto.

#### Scenario: Pregunta sobre el proceso
- **WHEN** el usuario escribe en el chat una pregunta sobre cómo funciona el onboarding
- **THEN** el sistema responde en el chat con una explicación en español

#### Scenario: Chat y formulario a la vez
- **WHEN** el usuario conversa en el chat durante un paso del formulario
- **THEN** el paso actual y los datos ya ingresados en el formulario no cambian

### Requirement: Consulta de los datos registrados
El sistema MUST mostrar al usuario, cuando los pida en el chat, los datos registrados de la wallet de su sesión actual: identificador de wallet, estado, DNI, tipo de documento, nombre, apellidos, teléfono, email y monto máximo. MUST NOT mostrar el identificador de verificación.

#### Scenario: Datos de una wallet registrada
- **WHEN** el usuario completó el onboarding en la sesión actual y pregunta por sus datos registrados
- **THEN** el sistema muestra los nueve campos con sus valores y no muestra el identificador de verificación

#### Scenario: Wallet con estado no activo
- **WHEN** la verificación de la sesión quedó registrada con estado PENDING o REJECTED y el usuario pregunta por sus datos
- **THEN** el sistema muestra los datos registrados con ese estado

#### Scenario: Sin datos registrados
- **WHEN** la sesión actual no tiene ningún registro y el usuario pregunta por sus datos
- **THEN** el sistema responde que todavía no hay datos registrados y no muestra ningún dato

### Requirement: Alcance limitado a la sesión
El sistema MUST resolver los datos consultados únicamente a partir de la sesión actual y MUST NOT usar identificadores escritos por el usuario o generados por el modelo para elegir qué registro mostrar.

#### Scenario: Consulta de datos de otra persona
- **WHEN** el usuario pide en el chat los datos de un DNI que no es el de su sesión
- **THEN** el sistema no muestra los datos de esa persona y solo ofrece los de su propia sesión

#### Scenario: Sesión distinta
- **WHEN** el usuario abre una sesión nueva que no completó el onboarding y pide sus datos
- **THEN** el sistema responde que todavía no hay datos registrados

### Requirement: Datos registrados fuera del modelo
El sistema MUST NOT enviar al modelo de lenguaje los datos registrados obtenidos en una consulta, ni en esa consulta ni en los mensajes posteriores de la conversación.

#### Scenario: Mensaje posterior a una consulta
- **WHEN** el usuario envía un mensaje al chat después de haber consultado sus datos registrados
- **THEN** la conversación que se envía al modelo no contiene los valores mostrados en la consulta

### Requirement: Indisponibilidad del modelo
El sistema MUST informar en el chat que el asistente no está disponible cuando el modelo de lenguaje no responde o falla, y MUST NOT interrumpir el formulario de onboarding.

#### Scenario: Modelo no disponible
- **WHEN** el modelo no responde o devuelve un error ante un mensaje del usuario
- **THEN** el chat muestra que el asistente no está disponible por ahora y el formulario sigue permitiendo completar el onboarding

### Requirement: Modelo configurable
El sistema MUST permitir elegir el modelo de lenguaje mediante una variable de entorno y MUST usar gpt-6-luna cuando no se configure otro.

#### Scenario: Modelo por defecto
- **WHEN** el backend arranca sin la variable de modelo definida
- **THEN** el asistente usa el modelo gpt-6-luna
