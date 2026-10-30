import { TestBed } from '@angular/core/testing';
import { AgentSubscriber } from '@ag-ui/client';
import { OnboardingAgent } from './onboarding-agent';
import { OnboardingPrompt, OnboardingState } from './onboarding.model';
import { AGENT_FACTORY, ASSISTANT_FACTORY, AgentLike, AssistantLike } from './onboarding-transport';
import { TraceStore } from './trace-store';

class FakeAssistant implements AssistantLike {
  readonly sent: unknown[] = [];
  constructor(
    readonly threadId: string,
    private readonly replies: (string | Error)[],
  ) {}

  addMessage(message: unknown): void {
    this.sent.push(message);
  }

  async runAgent(): Promise<never> {
    const reply = this.replies.shift() ?? '';
    if (reply instanceof Error) {
      throw reply;
    }
    return { result: undefined, newMessages: reply ? [{ id: 'a1', role: 'assistant', content: reply }] : [] } as never;
  }
}

interface Turn {
  prompt?: OnboardingPrompt;
  state: OnboardingState;
  error?: Error;
}

class FakeAgent implements AgentLike {
  state: OnboardingState = {};
  readonly runs: unknown[] = [];
  private readonly subscribers: AgentSubscriber[] = [];

  constructor(
    readonly threadId: string,
    private readonly turns: Turn[],
  ) {}

  subscribe(subscriber: AgentSubscriber) {
    this.subscribers.push(subscriber);
    return { unsubscribe: () => undefined };
  }

  async runAgent(params?: unknown): Promise<never> {
    this.runs.push(params);
    const turn = this.turns.shift();
    if (!turn || turn.error) {
      throw turn?.error ?? new Error('sin turnos');
    }
    const emit = (event: object) =>
      this.subscribers.forEach((subscriber) => {
        subscriber.onEvent?.({ event } as never);
        if ('name' in event) {
          subscriber.onCustomEvent?.({ event } as never);
        }
      });
    emit({ type: 'RUN_STARTED' });
    if (turn.prompt) {
      emit({ type: 'CUSTOM', name: 'on_interrupt', value: JSON.stringify(turn.prompt), rawEvent: { id: 'int-1' } });
    }
    emit({ type: 'RUN_FINISHED' });
    this.state = turn.state;
    return undefined as never;
  }
}

const flush = () => new Promise((resolve) => setTimeout(resolve));

function setup(turns: Turn[], nextThreads: Turn[][] = [], assistantReplies: (string | Error)[] = []) {
  const created: FakeAgent[] = [];
  const assistants: FakeAssistant[] = [];
  TestBed.configureTestingModule({
    providers: [
      {
        provide: ASSISTANT_FACTORY,
        useValue: (threadId: string) => {
          const fake = new FakeAssistant(threadId, assistantReplies);
          assistants.push(fake);
          return fake;
        },
      },
      {
        provide: AGENT_FACTORY,
        useValue: (threadId: string) => {
          const fake = new FakeAgent(threadId, created.length === 0 ? turns : (nextThreads[created.length - 1] ?? []));
          created.push(fake);
          return fake;
        },
      },
    ],
  });
  const agent = TestBed.inject(OnboardingAgent);
  return { agent, trace: TestBed.inject(TraceStore), created, assistants };
}

const step1: Turn = { prompt: { step: 1, fields: ['nombre', 'apellidos'], errors: [] }, state: { step: 1, done: false } };
const confirm: Turn = {
  prompt: { step: 5, confirm: true, errors: [] },
  state: { step: 5, done: false, data: { nombre: 'Ana', dni: '12345678' } },
};

describe('OnboardingAgent', () => {
  beforeEach(() => sessionStorage.clear());

  it('pregunta campo a campo y reanuda el interrupt con todas las claves del paso', async () => {
    const { agent, created } = setup([
      step1,
      { prompt: { step: 2, fields: ['telefono', 'email'], errors: [] }, state: { step: 2, done: false } },
    ]);
    await flush();

    expect(agent.currentStep()).toBe(1);
    expect(agent.messages().at(-1)?.text).toContain('nombre');

    await agent.send('Ana');
    expect(agent.messages().at(-1)?.text).toContain('apellidos');
    expect(created[0].runs).toHaveLength(1);

    await agent.send('Lopez');
    expect(created[0].runs.at(-1)).toEqual({
      resume: [{ interruptId: 'int-1', status: 'resolved', payload: { nombre: 'Ana', apellidos: 'Lopez' } }],
    });
    expect(agent.currentStep()).toBe(2);
    expect(agent.messages().at(-1)?.text).toContain('teléfono');
  });

  it('repite solo el campo que el backend rechazó', async () => {
    const { agent, created } = setup([
      step1,
      {
        prompt: {
          step: 1,
          fields: ['nombre', 'apellidos'],
          errors: [{ field: 'apellidos', message: 'El campo apellidos es obligatorio.' }],
        },
        state: { step: 1, done: false },
      },
      { prompt: { step: 2, fields: ['telefono', 'email'], errors: [] }, state: { step: 2, done: false } },
    ]);
    await flush();

    await agent.send('Ana');
    await agent.send('Lopez');
    expect(agent.messages().some((m) => m.text === 'El campo apellidos es obligatorio.')).toBe(true);
    expect(agent.currentField()).toBe('apellidos');

    await agent.send('Perez');
    expect(created[0].runs.at(-1)).toEqual({
      resume: [{ interruptId: 'int-1', status: 'resolved', payload: { nombre: 'Ana', apellidos: 'Perez' } }],
    });
    expect(agent.currentStep()).toBe(2);
  });

  it('valida teléfono y correo en el chat sin enviarlos al agente', async () => {
    const { agent, trace, created } = setup([
      { prompt: { step: 2, fields: ['telefono', 'email'], errors: [] }, state: { step: 2, done: false } },
      { prompt: { step: 3, fields: ['dni'], errors: [] }, state: { step: 3, done: false } },
    ]);
    await flush();

    await agent.send('99a999');
    expect(agent.messages().at(-1)?.text).toContain('solo números');
    expect(agent.currentField()).toBe('telefono');

    await agent.send('999999999');
    expect(agent.currentField()).toBe('email');

    for (const invalid of ['ana', 'ana@', 'ana@example', 'a na@example.com']) {
      await agent.send(invalid);
      expect(agent.messages().at(-1)?.text).toContain('formato válido');
      expect(agent.currentField()).toBe('email');
    }
    expect(created[0].runs).toHaveLength(1);
    expect(trace.events().filter((event) => event.kind === 'validation' && event.status === 'error')).toHaveLength(5);

    await agent.send(' ana@example.com ');
    expect(created[0].runs.at(-1)).toEqual({
      resume: [
        { interruptId: 'int-1', status: 'resolved', payload: { telefono: '999999999', email: 'ana@example.com' } },
      ],
    });
    expect(agent.currentStep()).toBe(3);
  });

  it('confirma la activación y registra la analítica', async () => {
    const { agent, trace, created } = setup([
      step1,
      confirm,
      { state: { step: 5, done: true, activated: true, wallet_id: 'wallet_1' } },
    ]);
    await flush();
    await agent.send('Ana');
    await agent.send('Lopez');

    expect(agent.phase()).toBe('CONFIRM');
    expect(agent.messages().at(-1)?.text).toContain('Ana');
    expect(agent.quickReplies().map((reply) => reply.label)).toContain('Activar wallet');

    await agent.send('Activar wallet');
    expect(created[0].runs.at(-1)).toEqual({
      resume: [{ interruptId: 'int-1', status: 'resolved', payload: { confirmar: true } }],
    });
    expect(agent.phase()).toBe('ACTIVE');
    expect(agent.walletId()).toBe('wallet_1');
    expect(trace.analytics().map((event) => `${event.name}:${event.step ?? event.result ?? ''}`)).toEqual([
      'onboarding_started:',
      'step_completed:datos_personales',
      'step_completed:contacto',
      'step_completed:documento',
      'step_completed:monto_maximo',
      'step_completed:activacion',
      'onboarding_closed:ACTIVE',
    ]);
    expect(agent.durationMs()).not.toBeNull();
  });

  it('tras la activación envía los mensajes libres al asistente en el mismo thread', async () => {
    const { agent, assistants } = setup(
      [confirm, { state: { step: 5, done: true, activated: true, wallet_id: 'wallet_1' } }],
      [],
      ['Tu límite es de 500 PEN.', new Error('network'), ''],
    );
    await flush();
    await agent.send('activar');
    expect(agent.phase()).toBe('ACTIVE');

    await agent.send('¿Cuál es el límite de pagos?');
    expect(assistants).toHaveLength(1);
    expect(assistants[0].threadId).toBe(agent.sessionId());
    expect(assistants[0].sent).toEqual([
      { id: expect.any(String), role: 'user', content: '¿Cuál es el límite de pagos?' },
    ]);
    expect(agent.messages().at(-1)).toMatchObject({ role: 'agent', text: 'Tu límite es de 500 PEN.' });
    expect(agent.phase()).toBe('ACTIVE');
    expect(agent.busy()).toBe(false);

    await agent.send('muéstrame mis datos');
    expect(assistants).toHaveLength(1);
    expect(agent.messages().at(-1)?.text).toContain('No pudimos conectar con el asistente');

    await agent.send('hola');
    expect(agent.messages().at(-1)?.text).toContain('No recibí una respuesta');
  });

  it('en ACTIVE «Ir a pagos» no consulta al asistente', async () => {
    const { agent, assistants } = setup([confirm, { state: { step: 5, done: true, activated: true } }]);
    await flush();
    await agent.send('activar');

    await agent.send('Ir a pagos');
    expect(assistants).toHaveLength(0);
    expect(agent.messages().at(-1)?.text).toContain('pagos de bajo monto');
  });

  it.each([
    ['REJECTED', 'REJECTED', 'no pudimos aprobar'],
    ['PENDING', 'PENDING', 'revisión manual'],
    ['REGISTRY_ERROR', 'FAILED', 'No pudimos completar'],
  ])('cierra con estado propio cuando el motivo es %s', async (reason, phase, text) => {
    const { agent, trace } = setup([confirm, { state: { step: 5, done: true, activated: false, reason } }]);
    await flush();

    await agent.send('activar');
    expect(agent.phase()).toBe(phase);
    expect(agent.messages().at(-1)?.text.toLowerCase()).toContain(text.toLowerCase());
    expect(agent.quickReplies().map((reply) => reply.label)).toEqual(['Empezar de nuevo']);
    expect(trace.analytics().at(-1)).toMatchObject({ name: 'onboarding_closed', result: reason === 'REGISTRY_ERROR' ? reason : phase });
  });

  it('con la API no disponible reintenta la activación en un thread nuevo reenviando los datos', async () => {
    const data = { nombre: 'Ana', apellidos: 'Lopez', dni: '12345678' };
    const { agent, trace, created } = setup(
      [
        { prompt: { step: 5, confirm: true, errors: [] }, state: { step: 5, done: false, data } },
        { state: { step: 5, done: true, activated: false, reason: 'API_UNAVAILABLE', data } },
      ],
      [
        [
          { prompt: { step: 1, fields: ['nombre', 'apellidos'], errors: [] }, state: { step: 1, done: false } },
          { prompt: { step: 5, confirm: true, errors: [] }, state: { step: 5, done: false, data } },
          { state: { step: 5, done: true, activated: true, wallet_id: 'wallet_1', data } },
        ],
      ],
    );
    await flush();

    await agent.send('activar');
    expect(agent.phase()).toBe('UNAVAILABLE');
    expect(agent.quickReplies().map((reply) => reply.label)).toEqual(['Reintentar', 'Empezar de nuevo']);
    expect(trace.analytics().some((event) => event.name === 'onboarding_closed')).toBe(false);

    await agent.send('Reintentar');

    expect(created).toHaveLength(2);
    expect(created[1].threadId).not.toBe(created[0].threadId);
    expect(created[1].runs).toEqual([
      undefined,
      { resume: [{ interruptId: 'int-1', status: 'resolved', payload: { nombre: 'Ana', apellidos: 'Lopez' } }] },
      { resume: [{ interruptId: 'int-1', status: 'resolved', payload: { confirmar: true } }] },
    ]);
    expect(agent.phase()).toBe('ACTIVE');
    expect(agent.walletId()).toBe('wallet_1');
    expect(trace.analytics().at(-1)).toMatchObject({ name: 'onboarding_closed', result: 'ACTIVE' });
  });

  it('permite reintentar cuando no hay conexión con el agente', async () => {
    const { agent, trace } = setup([{ state: {}, error: new Error('network') }, step1]);
    await flush();

    expect(agent.phase()).toBe('RETRY');
    expect(trace.events().some((event) => event.kind === 'run' && event.status === 'error')).toBe(true);

    await agent.send('Reintentar');
    expect(agent.phase()).toBe('COLLECTING');
    expect(agent.messages().at(-1)?.text).toContain('nombre');
  });

  it('sale de sesión abriendo un nuevo thread desde el primer paso', async () => {
    const { agent, trace, created } = setup([step1]);
    await flush();
    const previous = agent.sessionId();

    agent.exit();
    await flush();

    expect(agent.sessionId()).not.toBe(previous);
    expect(created).toHaveLength(2);
    expect(agent.currentStep()).toBe(1);
    expect(trace.analytics().some((event) => event.name === 'onboarding_closed' && event.result === 'ABANDONED')).toBe(
      true,
    );
  });
});
