import { InjectionToken, inject } from '@angular/core';
import { HttpAgent } from '@ag-ui/client';
import { environment } from '../../environments/environment';

/** Parte del agente AG-UI que usa el chat; permite sustituirlo en pruebas. */
export type AgentLike = Pick<HttpAgent, 'subscribe' | 'runAgent' | 'state'>;

/** Parte del agente AG-UI del asistente que usa el chat tras la activación. */
export type AssistantLike = Pick<HttpAgent, 'runAgent' | 'addMessage'>;

export const ONBOARDING_URL = new InjectionToken<string>('ONBOARDING_URL', {
  providedIn: 'root',
  factory: () => environment.onboardingUrl,
});

export const ASSISTANT_URL = new InjectionToken<string>('ASSISTANT_URL', {
  providedIn: 'root',
  factory: () => environment.assistantUrl,
});

export const ASSISTANT_FACTORY = new InjectionToken<(threadId: string) => AssistantLike>('ASSISTANT_FACTORY', {
  providedIn: 'root',
  factory: () => {
    const url = inject(ASSISTANT_URL);
    return (threadId) => new HttpAgent({ url, threadId });
  },
});

export const AGENT_FACTORY = new InjectionToken<(threadId: string) => AgentLike>('AGENT_FACTORY', {
  providedIn: 'root',
  factory: () => {
    const url = inject(ONBOARDING_URL);
    return (threadId) => new HttpAgent({ url, threadId });
  },
});
