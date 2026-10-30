export type Phase = 'COLLECTING' | 'CONFIRM' | 'ACTIVE' | 'REJECTED' | 'PENDING' | 'UNAVAILABLE' | 'FAILED' | 'RETRY';

/** Pasos del grafo de onboarding del backend, en orden. */
export const STEPS = ['Datos personales', 'Contacto', 'Documento', 'Monto máximo', 'Activación'] as const;

export const STEP_KEYS = ['datos_personales', 'contacto', 'documento', 'monto_maximo', 'activacion'] as const;

export const ACTIVATION_STEP = STEPS.length;

export interface OnboardingError {
  readonly field: string | null;
  readonly message: string;
}

/** Valor del interrupt `on_interrupt` que emite cada nodo del grafo. */
export interface OnboardingPrompt {
  readonly step: number;
  readonly fields?: readonly string[];
  readonly confirm?: boolean;
  readonly errors?: readonly OnboardingError[];
  readonly moneda?: string;
}

/** Estado del grafo que el backend publica mediante STATE_SNAPSHOT. */
export interface OnboardingState {
  readonly step?: number;
  readonly data?: Readonly<Record<string, string>>;
  readonly errors?: readonly OnboardingError[];
  readonly activated?: boolean;
  readonly wallet_id?: string | null;
  readonly reason?: string | null;
  readonly done?: boolean;
}

export interface FieldInfo {
  readonly label: string;
  readonly question: string;
  readonly inputMode: 'text' | 'numeric' | 'email' | 'tel' | 'decimal';
}

export const FIELDS: Record<string, FieldInfo> = {
  nombre: { label: 'nombre', question: '¿Cuál es tu nombre?', inputMode: 'text' },
  apellidos: { label: 'apellidos', question: '¿Y tus apellidos?', inputMode: 'text' },
  telefono: { label: 'teléfono', question: '¿Cuál es tu número de teléfono?', inputMode: 'tel' },
  email: { label: 'correo electrónico', question: '¿Cuál es tu correo electrónico?', inputMode: 'email' },
  dni: { label: 'DNI (8 dígitos)', question: 'Escribe tu DNI (8 dígitos).', inputMode: 'numeric' },
  monto_maximo: {
    label: 'monto máximo en PEN',
    question: '¿Cuál es el monto máximo por operación que quieres usar? Indícalo en PEN (hasta 500).',
    inputMode: 'decimal',
  },
};

const PHONE_PATTERN = /^\d+$/;
const EMAIL_PATTERN = /^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$/;

/** Validación en el cliente antes de enviar el campo al agente; devuelve el error o null si es válido. */
export function validateField(field: string, value: string): string | null {
  const text = value.trim();
  if (field === 'telefono') {
    if (!text) {
      return 'El teléfono es obligatorio.';
    }
    return PHONE_PATTERN.test(text) ? null : 'El teléfono debe contener solo números.';
  }
  if (field === 'email') {
    if (!text) {
      return 'El correo electrónico es obligatorio.';
    }
    return EMAIL_PATTERN.test(text) ? null : 'El correo electrónico no tiene un formato válido.';
  }
  return null;
}

const UNAVAILABLE_REASONS = ['API_UNAVAILABLE', 'KYC_UNAVAILABLE'];

export type FailurePhase = 'REJECTED' | 'PENDING' | 'UNAVAILABLE' | 'FAILED';

/** Traduce el motivo con que el backend cierra una activación fallida al estado del chat. */
export function classifyFailure(reason: string | null | undefined): FailurePhase {
  if (reason === 'REJECTED' || reason === 'PENDING') {
    return reason;
  }
  return reason && UNAVAILABLE_REASONS.includes(reason) ? 'UNAVAILABLE' : 'FAILED';
}

export const FAILURE_MESSAGES: Record<FailurePhase, string> = {
  REJECTED:
    'No pudimos aprobar tu verificación con los datos enviados, por lo que tu wallet no fue activada. Puedes intentarlo de nuevo desde el inicio.',
  PENDING:
    'Tu verificación necesita una revisión manual antes de activarse. Aún no podemos activar tu wallet; empieza de nuevo cuando quieras volver a intentarlo.',
  UNAVAILABLE:
    'El servicio de verificación no está disponible en este momento. Tus datos siguen guardados: puedes reintentar la activación.',
  FAILED: 'No pudimos completar la activación de tu wallet. Puedes intentarlo de nuevo desde el inicio.',
};
