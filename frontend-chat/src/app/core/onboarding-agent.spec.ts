import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { OnboardingAgent } from './onboarding-agent';
import { TraceStore } from './trace-store';

type Matcher = { method: string; suffix: string };

async function nextRequest(http: HttpTestingController, { method, suffix }: Matcher): Promise<TestRequest> {
  for (let attempt = 0; attempt < 100; attempt++) {
    const [match] = http.match((req) => req.method === method && req.url.endsWith(suffix));
    if (match) {
      return match;
    }
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error(`No se recibió ${method} ${suffix}`);
}

const verification = (status: string) => ({ id: 'kyc_1', wallet_id: 'wallet_1', scenario: 'APPROVED', status });
const wallet = { id: 'wallet_1', status: 'ACTIVE', balance: 0, reserved: 0, available: 0, currency: 'PEN' };

describe('OnboardingAgent', () => {
  let http: HttpTestingController;
  let agent: OnboardingAgent;
  let trace: TraceStore;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    agent = TestBed.inject(OnboardingAgent);
    trace = TestBed.inject(TraceStore);
  });

  afterEach(() => http.verify());

  it('bloquea el avance con un DNI inválido y explica cómo corregirlo', async () => {
    await agent.send('1234');

    expect(agent.currentStep()).toBe(1);
    expect(agent.phase()).toBe('ASK_DNI');
    expect(agent.messages().at(-1)?.text).toContain('8 números');
    expect(trace.events().some((event) => event.kind === 'validation' && event.status === 'error')).toBe(true);
    http.expectNone(() => true);
  });

  it('completa el flujo aprobado con los cuatro pasos y la analítica', async () => {
    const sending = agent.send('12345678');

    const create = await nextRequest(http, { method: 'POST', suffix: '/kyc/verifications' });
    expect(create.request.body).toEqual({ documentType: 'TEST', document: 'TEST-12345678', scenario: 'APPROVED' });
    create.flush(verification('ACTIVE'));
    (await nextRequest(http, { method: 'GET', suffix: '/kyc/verifications/kyc_1' })).flush(verification('ACTIVE'));
    (await nextRequest(http, { method: 'GET', suffix: '/wallets/wallet_1' })).flush(wallet);
    await sending;

    expect(agent.phase()).toBe('ACTIVE');
    expect(agent.currentStep()).toBe(4);
    expect(agent.messages().some((message) => message.text.includes('TEST'))).toBe(false);
    expect(trace.analytics().map((event) => `${event.name}:${event.step ?? event.result ?? ''}`)).toEqual([
      'onboarding_started:',
      'step_completed:registro',
      'step_completed:verificacion',
      'step_completed:wallet',
      'onboarding_closed:ACTIVE',
    ]);
    expect(agent.durationMs()).not.toBeNull();
  });

  it('resuelve una revisión manual con la decisión del usuario', async () => {
    const sending = agent.send('12345678');
    (await nextRequest(http, { method: 'POST', suffix: '/kyc/verifications' })).flush(verification('PENDING'));
    (await nextRequest(http, { method: 'GET', suffix: '/kyc/verifications/kyc_1' })).flush(verification('PENDING'));
    await sending;

    expect(agent.phase()).toBe('PENDING_DECISION');
    expect(agent.quickReplies().map((reply) => reply.label)).toContain('Aprobar');

    const deciding = agent.send('Aprobar');
    const decision = await nextRequest(http, { method: 'POST', suffix: '/kyc/verifications/kyc_1/decision' });
    expect(decision.request.body).toEqual({ decision: 'ACTIVE' });
    decision.flush(verification('ACTIVE'));
    (await nextRequest(http, { method: 'GET', suffix: '/wallets/wallet_1' })).flush(wallet);
    await deciding;

    expect(agent.phase()).toBe('ACTIVE');
  });

  it('permite reintentar cuando el servicio no está disponible', async () => {
    const sending = agent.send('12345678');
    (await nextRequest(http, { method: 'POST', suffix: '/kyc/verifications' })).flush(
      { message: 'unavailable' },
      { status: 503, statusText: 'Service Unavailable' },
    );
    await sending;

    expect(agent.phase()).toBe('RETRY');
    expect(agent.quickReplies().map((reply) => reply.label)).toEqual(['Reintentar', 'Corregir mi DNI']);
    expect(trace.events().some((event) => event.kind === 'http-response' && event.status === 'error')).toBe(true);
  });

  it('vuelve al registro y sale de sesión reiniciando desde el primer paso', async () => {
    const sending = agent.send('12345678');
    (await nextRequest(http, { method: 'POST', suffix: '/kyc/verifications' })).flush(verification('PENDING'));
    (await nextRequest(http, { method: 'GET', suffix: '/kyc/verifications/kyc_1' })).flush(verification('PENDING'));
    await sending;

    agent.goBack();
    expect(agent.phase()).toBe('ASK_DNI');
    expect(agent.currentStep()).toBe(1);

    const previousSession = agent.sessionId();
    agent.exit();
    expect(agent.sessionId()).not.toBe(previousSession);
    expect(agent.messages()).toHaveLength(1);
    expect(trace.analytics().some((event) => event.name === 'onboarding_closed' && event.result === 'ABANDONED')).toBe(true);
  });
});
