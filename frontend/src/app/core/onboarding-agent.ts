import { Injectable, inject, signal } from '@angular/core';
import { AgentSubscriber, BaseEvent, EventType } from '@ag-ui/client';
import {
  ACTIVATION_STEP,
  FIELDS,
  FAILURE_MESSAGES,
  OnboardingPrompt,
  OnboardingState,
  Phase,
  STEP_KEYS,
  classifyFailure,
  validateField,
} from './onboarding.model';
import {
  AGENT_FACTORY,
  ASSISTANT_FACTORY,
  ASSISTANT_URL,
  AgentLike,
  AssistantLike,
  ONBOARDING_URL,
} from './onboarding-transport';
import { TraceStore } from './trace-store';

export { STEPS } from './onboarding.model';
export type { Phase } from './onboarding.model';

export interface ChatMessage {
  id: number;
  role: 'agent' | 'user';
  text: string;
}

export interface QuickReply {
  label: string;
  text: string;
}

const QR_ACTIVATE: QuickReply = { label: 'Activar wallet', text: 'Activar wallet' };
const QR_RETRY: QuickReply = { label: 'Reintentar', text: 'Reintentar' };
const QR_PAY: QuickReply = { label: 'Ir a pagos de bajo monto', text: 'Ir a pagos' };
const QR_RESTART: QuickReply = { label: 'Empezar de nuevo', text: 'Reiniciar' };

const RESTART = /^(reiniciar|salir|empezar de nuevo|nuevo registro|intentar de nuevo)/;
const CONFIRM = /^(si|activ|confirm|acept|ok)/;
const RETRY = /^reintent/;
const GO_TO_PAYMENTS = /^ir a pagos/;

const ASSISTANT_ERROR = 'No pudimos conectar con el asistente. Inténtalo de nuevo en unos instantes.';
const ASSISTANT_EMPTY = 'No recibí una respuesta del asistente. ¿Puedes reformular tu mensaje?';

const THREAD_STORAGE_KEY = 'onboarding.threadId';

const DATA_LABELS: [string, string][] = [
  ['nombre', 'Nombre'],
  ['apellidos', 'Apellidos'],
  ['telefono', 'Teléfono'],
  ['email', 'Correo'],
  ['dni', 'DNI'],
  ['monto_maximo', 'Monto máximo (PEN)'],
];

const normalize = (text: string) =>
  text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

// El adaptador AG-UI envía el valor del interrupt como cadena JSON.
function parsePrompt(value: unknown): OnboardingPrompt | null {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value) as OnboardingPrompt;
    } catch {
      return null;
    }
  }
  return (value ?? null) as OnboardingPrompt | null;
}

/**
 * Conversa con el agente de onboarding del backend (LangGraph vía AG-UI). El grafo valida cada paso
 * y decide el siguiente; el chat solo pregunta campo a campo y reanuda el interrupt con las respuestas.
 */
@Injectable({ providedIn: 'root' })
export class OnboardingAgent {
  private readonly createAgent = inject(AGENT_FACTORY);
  private readonly createAssistant = inject(ASSISTANT_FACTORY);
  private readonly url = inject(ONBOARDING_URL);
  private readonly assistantUrl = inject(ASSISTANT_URL);
  private readonly trace = inject(TraceStore);

  readonly messages = signal<ChatMessage[]>([]);
  readonly quickReplies = signal<QuickReply[]>([]);
  readonly phase = signal<Phase>('COLLECTING');
  readonly currentStep = signal(1);
  readonly currentField = signal<string | null>(null);
  readonly busy = signal(false);
  readonly sessionId = signal('');
  readonly walletId = signal<string | null>(null);
  readonly durationMs = signal<number | null>(null);

  private msgSeq = 0;
  private closed = false;
  private agent: AgentLike | null = null;
  private assistant: { threadId: string; agent: AssistantLike } | null = null;
  private subscription: { unsubscribe(): void } | null = null;
  private interruptId: string | undefined;
  private incoming: OnboardingPrompt | null = null;
  private currentPrompt: OnboardingPrompt | null = null;
  private lastStep = 0;
  private pending: string[] = [];
  private answers: Record<string, string> = {};
  private retryAction: (() => Promise<void>) | null = null;
  private lastData: Record<string, string> | null = null;
  private replay: Record<string, string> | null = null;

  constructor() {
    void this.start();
  }

  async send(raw: string): Promise<void> {
    const text = raw.trim();
    if (!text || this.busy()) {
      return;
    }

    this.busy.set(true);
    this.quickReplies.set([]);
    this.pushMessage('user', text);
    try {
      await this.route(text);
    } finally {
      this.busy.set(false);
    }
  }

  exit(): void {
    if (!this.busy()) {
      this.leave();
    }
  }

  private leave(): void {
    this.trace.log({
      from: 'ui',
      to: 'agent',
      kind: 'message',
      label: 'Sesión descartada: se abre un nuevo thread',
      payload: { threadId: this.sessionId() },
    });
    this.close('ABANDONED');
    sessionStorage.removeItem(THREAD_STORAGE_KEY);
    void this.start();
  }

  private start(): Promise<void> {
    const stored = sessionStorage.getItem(THREAD_STORAGE_KEY);
    const threadId = stored ?? crypto.randomUUID();
    this.sessionId.set(threadId);
    this.trace.beginSession(threadId);
    this.messages.set([]);
    this.quickReplies.set([]);
    this.currentStep.set(1);
    this.walletId.set(null);
    this.durationMs.set(null);
    this.closed = false;
    this.retryAction = null;
    this.replay = null;
    this.lastData = null;

    this.trace.track('onboarding_started');
    this.connect(threadId);
    this.reply(
      stored
        ? 'Hola de nuevo, retomemos tu registro donde lo dejaste.'
        : 'Hola, soy tu asistente. Te ayudo a activar tu wallet en pocos pasos.',
    );
    return this.run();
  }

  /** Abre la conexión AG-UI para un thread; el estado de la conversación del chat no se toca. */
  private connect(threadId: string): void {
    sessionStorage.setItem(THREAD_STORAGE_KEY, threadId);
    this.sessionId.set(threadId);
    this.interruptId = undefined;
    this.incoming = null;
    this.currentPrompt = null;
    this.lastStep = 0;
    this.pending = [];
    this.answers = {};
    this.currentField.set(null);
    this.phase.set('COLLECTING');
    this.assistant = null;

    this.subscription?.unsubscribe();
    const agent = this.createAgent(threadId);
    this.agent = agent;
    this.subscription = agent.subscribe(this.subscriber());
  }

  private subscriber(): AgentSubscriber {
    return {
      onEvent: ({ event }) => this.traceEvent(event),
      onCustomEvent: ({ event }) => {
        if (event.name !== 'on_interrupt') {
          return;
        }
        this.incoming = parsePrompt(event.value);
        this.interruptId = (event as { rawEvent?: { id?: string } }).rawEvent?.id;
      },
    };
  }

  private async run(payload?: Record<string, unknown>): Promise<void> {
    const agent = this.agent;
    if (!agent) {
      return;
    }

    this.incoming = null;
    this.busy.set(true);
    this.trace.log({
      from: 'ui',
      to: 'agent',
      kind: 'request',
      label: `POST ${this.url}`,
      payload: { threadId: this.sessionId(), resume: payload ?? null },
    });

    const startedAt = performance.now();
    try {
      await agent.runAgent(
        payload ? { resume: [{ interruptId: this.interruptId ?? '', status: 'resolved', payload }] } : undefined,
      );
    } catch (error) {
      if (agent !== this.agent) {
        return;
      }
      this.trace.log({
        from: 'agent',
        to: 'ui',
        kind: 'run',
        status: 'error',
        label: 'La ejecución del agente falló',
        durationMs: Math.round(performance.now() - startedAt),
        payload: String(error),
      });
      this.failRetry('No pudimos conectar con el asistente. Comprueba tu conexión e inténtalo de nuevo.', () =>
        this.run(payload),
      );
      return;
    } finally {
      this.busy.set(false);
    }

    if (agent !== this.agent) {
      return;
    }
    const state = (agent.state ?? {}) as OnboardingState;
    this.trace.log({ from: 'agent', to: 'ui', kind: 'state', label: 'Estado del onboarding', payload: this.publicState(state) });

    const incoming = this.incoming as OnboardingPrompt | null;
    if (state.done) {
      this.replay = null;
      this.finish(state);
    } else if (incoming && this.replay && !incoming.errors?.length) {
      await this.replayStep(incoming);
    } else if (incoming) {
      this.replay = null;
      this.applyPrompt(incoming, state);
    } else {
      this.failRetry('No recibimos la siguiente pregunta del asistente.', () => this.run());
    }
  }

  private async route(text: string): Promise<void> {
    const normalized = normalize(text);
    if (RESTART.test(normalized)) {
      this.leave();
      return;
    }

    switch (this.phase()) {
      case 'COLLECTING':
        return this.onAnswer(text);
      case 'CONFIRM':
        return this.onConfirm(normalized);
      case 'RETRY':
        return this.onRetry(normalized);
      case 'ACTIVE':
        return this.onActive(text, normalized);
      case 'UNAVAILABLE':
        return this.onUnavailable(normalized);
      case 'REJECTED':
      case 'PENDING':
      case 'FAILED':
        this.reply('La activación no se completó. Escribe «reiniciar» para intentarlo otra vez.', [QR_RESTART]);
    }
  }

  private async onAnswer(text: string): Promise<void> {
    const field = this.pending[0];
    const fields = this.currentPrompt?.fields ?? [];
    if (!field) {
      return;
    }

    const error = validateField(field, text);
    if (error) {
      this.trace.log({
        from: 'ui',
        to: 'ui',
        kind: 'validation',
        status: 'error',
        label: `Validación del chat: ${field} inválido, no se envía al agente`,
        payload: { field, input: text },
      });
      this.reply(`${error} Inténtalo de nuevo.`);
      return;
    }

    this.pending.shift();
    this.answers[field] = text.trim();
    this.trace.log({
      from: 'ui',
      to: 'ui',
      kind: 'message',
      label: `Respuesta capturada: ${field} (se envía al completar el paso)`,
    });

    if (this.pending.length) {
      this.askNext();
      return;
    }

    this.currentField.set(null);
    // El grafo espera todas las claves del paso: un payload vacío no llega al nodo.
    await this.run(Object.fromEntries(fields.map((name) => [name, this.answers[name] ?? ''])));
  }

  private async onConfirm(normalized: string): Promise<void> {
    if (CONFIRM.test(normalized)) {
      await this.run({ confirmar: true });
    } else {
      this.reply('Para activar tu wallet pulsa «Activar wallet» o escribe «activar».', [QR_ACTIVATE, QR_RESTART]);
    }
  }

  private async onRetry(normalized: string): Promise<void> {
    const action = this.retryAction;
    if (RETRY.test(normalized) && action) {
      this.retryAction = null;
      await action();
    } else {
      this.reply('Pulsa «Reintentar» para volver a intentarlo.', [QR_RETRY, QR_RESTART]);
    }
  }

  private async onActive(text: string, normalized: string): Promise<void> {
    if (GO_TO_PAYMENTS.test(normalized)) {
      this.reply('El punto de entrada de pagos de bajo monto se habilitará en la siguiente etapa.', [QR_PAY, QR_RESTART]);
      return;
    }
    await this.askAssistant(text);
  }

  /** Tras la activación, el mensaje libre lo responde el agente del asistente en el mismo thread de la sesión. */
  private async askAssistant(text: string): Promise<void> {
    const threadId = this.sessionId();
    if (this.assistant?.threadId !== threadId) {
      this.assistant = { threadId, agent: this.createAssistant(threadId) };
    }
    const { agent } = this.assistant;
    agent.addMessage({ id: crypto.randomUUID(), role: 'user', content: text });

    this.trace.log({
      from: 'ui',
      to: 'agent',
      kind: 'request',
      label: `POST ${this.assistantUrl}`,
      payload: { threadId },
    });
    const startedAt = performance.now();
    try {
      const { newMessages } = await agent.runAgent();
      const answers = newMessages
        .filter((message) => message.role === 'assistant' && typeof message.content === 'string' && message.content.trim())
        .map((message) => message.content as string);
      this.trace.log({
        from: 'agent',
        to: 'ui',
        kind: 'run',
        label: 'Respuesta del asistente',
        durationMs: Math.round(performance.now() - startedAt),
      });
      for (const answer of answers.length ? answers : [ASSISTANT_EMPTY]) {
        this.reply(answer, [QR_PAY, QR_RESTART]);
      }
    } catch (error) {
      this.trace.log({
        from: 'agent',
        to: 'ui',
        kind: 'run',
        status: 'error',
        label: 'La ejecución del asistente falló',
        durationMs: Math.round(performance.now() - startedAt),
        payload: String(error),
      });
      this.reply(ASSISTANT_ERROR, [QR_PAY, QR_RESTART]);
    }
  }

  private applyPrompt(prompt: OnboardingPrompt, state: OnboardingState): void {
    const errors = prompt.errors ?? [];

    if (this.lastStep > 0 && prompt.step > this.lastStep) {
      for (let step = this.lastStep; step < prompt.step; step++) {
        this.trace.track('step_completed', { step: STEP_KEYS[step - 1] });
      }
      this.trace.log({
        from: 'graph',
        to: 'ui',
        kind: 'validation',
        label: `Validación del backend: paso ${this.lastStep} aceptado`,
      });
      this.answers = {};
    } else if (this.lastStep > 0 && prompt.step < this.lastStep) {
      this.answers = {};
    }
    this.lastStep = prompt.step;
    this.currentPrompt = prompt;
    this.currentStep.set(prompt.step);

    if (errors.length) {
      this.trace.log({
        from: 'graph',
        to: 'ui',
        kind: 'validation',
        status: 'error',
        label: 'Validación del backend: datos rechazados, el paso no avanza',
        payload: errors,
      });
      this.reply(errors.map((error) => error.message).join('\n'));
    }

    if (prompt.confirm) {
      this.phase.set('CONFIRM');
      this.pending = [];
      this.currentField.set(null);
      this.reply(this.confirmationText(state), [QR_ACTIVATE, QR_RESTART]);
      return;
    }

    this.phase.set('COLLECTING');
    const fields = prompt.fields ?? [];
    const rejected = errors.map((error) => error.field).filter((name): name is string => !!name && fields.includes(name));
    if (rejected.length) {
      rejected.forEach((name) => delete this.answers[name]);
      this.pending = rejected;
    } else {
      this.answers = {};
      this.pending = [...fields];
    }
    this.askNext();
  }

  private askNext(): void {
    const field = this.pending[0];
    this.currentField.set(field ?? null);
    this.reply(FIELDS[field]?.question ?? `Indica ${field}.`);
  }

  private confirmationText(state: OnboardingState): string {
    const data = state.data ?? {};
    const lines = DATA_LABELS.filter(([key]) => data[key]).map(([key, label]) => `• ${label}: ${data[key]}`);
    return ['Revisa tus datos:', ...lines, '¿Confirmas la activación de tu wallet?'].join('\n');
  }

  private finish(state: OnboardingState): void {
    this.pending = [];
    this.currentField.set(null);
    this.currentStep.set(ACTIVATION_STEP);

    if (state.activated) {
      if (this.lastStep === ACTIVATION_STEP) {
        this.trace.track('step_completed', { step: STEP_KEYS[ACTIVATION_STEP - 1] });
      }
      this.walletId.set(state.wallet_id ?? null);
      this.close('ACTIVE');
      this.phase.set('ACTIVE');
      this.reply('¡Listo! Tu wallet está activa. Ya puedes ir al punto de entrada de pagos de bajo monto.', [
        QR_PAY,
        QR_RESTART,
      ]);
    } else {
      const outcome = classifyFailure(state.reason);
      this.lastData = state.data ?? null;
      this.phase.set(outcome);
      this.reply(
        FAILURE_MESSAGES[outcome],
        outcome === 'UNAVAILABLE' && this.lastData ? [QR_RETRY, QR_RESTART] : [QR_RESTART],
      );
      // Con la API caída la sesión sigue abierta: el usuario puede reintentar sin volver a escribir sus datos.
      if (outcome !== 'UNAVAILABLE') {
        this.close(outcome === 'FAILED' ? (state.reason ?? 'FAILED') : outcome);
      }
    }
  }

  private async onUnavailable(normalized: string): Promise<void> {
    if (!RETRY.test(normalized) || !this.lastData) {
      this.reply('Pulsa «Reintentar» para volver a activar tu wallet.', [QR_RETRY, QR_RESTART]);
      return;
    }

    // El thread terminó al activar: se abre uno nuevo y se reenvían los datos ya capturados.
    this.trace.log({
      from: 'ui',
      to: 'agent',
      kind: 'message',
      label: 'Reintento de activación: nuevo thread con los datos ya capturados',
      payload: { threadId: this.sessionId() },
    });
    this.replay = this.lastData;
    this.lastData = null;
    this.reply('Reintentando la activación con tus datos…');
    this.connect(crypto.randomUUID());
    await this.run();
  }

  private replayStep(prompt: OnboardingPrompt): Promise<void> {
    this.lastStep = prompt.step;
    this.currentPrompt = prompt;
    this.currentStep.set(prompt.step);
    const data = this.replay ?? {};
    return this.run(
      prompt.confirm ? { confirmar: true } : Object.fromEntries((prompt.fields ?? []).map((name) => [name, data[name] ?? ''])),
    );
  }

  private failRetry(message: string, retry: () => Promise<void>): void {
    this.retryAction = retry;
    this.phase.set('RETRY');
    this.currentField.set(null);
    this.reply(message, [QR_RETRY, QR_RESTART]);
  }

  private close(result: string): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.trace.track('onboarding_closed', { result });
    this.durationMs.set(Date.now() - this.trace.sessionStartedAt());
  }

  private traceEvent(event: BaseEvent): void {
    const data = event as BaseEvent & { stepName?: string; name?: string; value?: unknown; message?: string; code?: string };
    switch (event.type) {
      case EventType.RUN_STARTED:
        this.trace.log({ from: 'agent', to: 'ui', kind: 'run', label: 'RUN_STARTED' });
        break;
      case EventType.STEP_STARTED:
        this.trace.log({ from: 'graph', to: 'ui', kind: 'step', label: `Nodo «${data.stepName}»` });
        break;
      case EventType.CUSTOM:
        if (data.name === 'on_interrupt') {
          const prompt = parsePrompt(data.value);
          this.trace.log({
            from: 'graph',
            to: 'ui',
            kind: 'interrupt',
            label: prompt?.confirm
              ? `Interrupt del paso ${prompt.step}: espera la confirmación`
              : `Interrupt del paso ${prompt?.step}: espera ${prompt?.fields?.join(', ')}`,
            payload: prompt,
          });
        }
        break;
      case EventType.RUN_FINISHED:
        this.trace.log({ from: 'agent', to: 'ui', kind: 'run', label: 'RUN_FINISHED' });
        break;
      case EventType.RUN_ERROR:
        this.trace.log({
          from: 'agent',
          to: 'ui',
          kind: 'run',
          status: 'error',
          label: 'RUN_ERROR',
          payload: { message: data.message, code: data.code },
        });
        break;
    }
  }

  private publicState(state: OnboardingState): OnboardingState {
    const { step, data, errors, activated, wallet_id, reason, done } = state;
    return { step, data, errors, activated, wallet_id, reason, done };
  }

  private reply(text: string, quickReplies: QuickReply[] = []): void {
    this.pushMessage('agent', text);
    this.quickReplies.set(quickReplies);
  }

  private pushMessage(role: ChatMessage['role'], text: string): void {
    this.messages.update((messages) => [...messages, { id: ++this.msgSeq, role, text }]);
  }
}
