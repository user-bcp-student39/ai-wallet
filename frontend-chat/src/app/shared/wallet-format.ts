import { HttpErrorResponse } from '@angular/common/http';
import { KycScenario } from '../wallet-api.service';

export const SCENARIO_LABELS: Record<KycScenario, string> = {
  APPROVED: 'Aprobada',
  MANUAL_REVIEW: 'Revisión pendiente',
  REJECTED: 'No aprobada',
  UNAVAILABLE: 'Servicio no disponible',
};

export function formatPEN(cents: number): string {
  return new Intl.NumberFormat('es-PE', {
    style: 'currency',
    currency: 'PEN',
  }).format(cents / 100);
}

export function describeHttpError(error: unknown, fallback: string): string {
  if (!(error instanceof HttpErrorResponse)) {
    return fallback;
  }

  if (error.status === 0) {
    return 'No se pudo conectar con el servicio. Comprueba tu conexión e inténtalo de nuevo.';
  }

  const messages: Record<number, string> = {
    400: 'La solicitud no es válida. Revisa los datos e inténtalo de nuevo.',
    404: 'No encontramos la información solicitada. Vuelve a intentarlo desde el inicio.',
    409: 'La solicitud ya tiene una decisión final diferente. Actualizaremos su estado.',
    503: 'El servicio no está disponible en este momento. Puedes reintentar en unos minutos.',
  };
  return messages[error.status] ?? fallback;
}
