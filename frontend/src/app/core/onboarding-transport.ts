import { InjectionToken, inject } from '@angular/core';
import { HttpAgent } from '@ag-ui/client';
import { environment } from '../../environments/environment';

/** Parte del agente AG-UI que usa el chat; permite sustituirlo en pruebas. */
export type AgentLike = Pick<HttpAgent, 'subscribe' | 'runAgent' | 'state'>;

export const ONBOARDING_URL = new InjectionToken<string>('ONBOARDING_URL', {
  providedIn: 'root',
  factory: () => environment.onboardingUrl,
});

export const AGENT_FACTORY = new InjectionToken<(threadId: string) => AgentLike>('AGENT_FACTORY', {
  providedIn: 'root',
  factory: () => {
    const url = inject(ONBOARDING_URL);
    return (threadId) => new HttpAgent({ url, threadId });
  },
});
