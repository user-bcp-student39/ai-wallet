import { Injectable, inject, signal } from '@angular/core';
import { KycScenario, KycVerification, Wallet } from '../wallet-api.service';
import { describeHttpError, formatPEN } from '../shared/wallet-format';
import { McpTools, ToolResult } from './mcp-tools';
import { TOOL_DEFINITIONS, ToolName } from './trace.model';
import { TraceStore } from './trace-store';

export type Phase = 'ASK_DNI' | 'PENDING_DECISION' | 'ACTIVE' | 'REJECTED' | 'RETRY';

export const STEPS = ['Registro', 'Verificación', 'Wallet', 'Pagos'] as const;

export interface ChatMessage {
  id: number;
  role: 'agent' | 'user';
  text: string;
}

export interface QuickReply {
  label: string;
  text: string;
}

type FailedResult = Extract<ToolResult<unknown>, { ok: false }>;

const QR_APPROVE: QuickReply = { label: 'Aprobar', text: 'Aprobar' };
const QR_REJECT: QuickReply = { label: 'Rechazar', text: 'Rechazar' };
const QR_FIX: QuickReply = { label: 'Corregir mi DNI', text: 'Corregir mi DNI' };
const QR_RETRY: QuickReply = { label: 'Reintentar', text: 'Reintentar' };
const QR_PAY: QuickReply = { label: 'Ir a pagos de bajo monto', text: 'Ir a pagos' };
const QR_RESTART: QuickReply = { label: 'Empezar de nuevo', text: 'Reiniciar' };

const RESTART = /^(reiniciar|salir|empezar de nuevo|nuevo registro|intentar de nuevo)/;

const normalize = (text: string) =>
  text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

const newSessionId = () => `sess_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;

/**
 * Simula la API Java y el agente: las reglas (validación, paso actual, analítica)
 * son deterministas y el "LLM" solo decide qué tool MCP invocar.
 */
@Injectable({ providedIn: 'root' })
export class OnboardingAgent {
  private readonly tools = inject(McpTools);
  private readonly trace = inject(TraceStore);

  readonly messages = signal<ChatMessage[]>([]);
  readonly quickReplies = signal<QuickReply[]>([]);
  readonly phase = signal<Phase>('ASK_DNI');
  readonly currentStep = signal(1);
  readonly busy = signal(false);
  readonly scenario = signal<KycScenario>('APPROVED');
  readonly sessionId = signal('');
  readonly verification = signal<KycVerification | null>(null);
  readonly wallet = signal<Wallet | null>(null);
  readonly durationMs = signal<number | null>(null);

  private msgSeq = 0;
  private closed = false;
  private retryAction: (() => Promise<void>) | null = null;

  constructor() {
    this.start();
  }

  async send(raw: string): Promise<void> {
    const text = raw.trim();
    if (!text || this.busy()) {
      return;
    }

    this.busy.set(true);
    this.quickReplies.set([]);
    this.pushMessage('user', text);
    this.trace.log({
      from: 'ui',
      to: 'api',
      kind: 'message',
      label: `POST /chat/sessions/${this.sessionId()}/messages`,
      payload: { text },
    });

    try {
      await this.route(text);
    } finally {
      this.busy.set(false);
    }
  }

  goBack(): void {
    if (this.busy() || this.phase() === 'ASK_DNI' || this.phase() === 'ACTIVE') {
      return;
    }
    this.trace.log({
      from: 'ui',
      to: 'api',
      kind: 'message',
      label: `POST /chat/sessions/${this.sessionId()}/back`,
      payload: { from: this.phase() },
    });
    this.askDni('Volvamos al registro. Escribe tu DNI de 8 dígitos.');
  }

  exit(): void {
    if (!this.busy()) {
      this.leave();
    }
  }

  private leave(): void {
    this.trace.log({
      from: 'ui',
      to: 'api',
      kind: 'message',
      label: `DELETE /chat/sessions/${this.sessionId()}`,
      payload: { reason: 'logout' },
    });
    this.close('ABANDONED');
    this.start();
  }

  private start(): void {
    const id = newSessionId();
    this.sessionId.set(id);
    this.trace.beginSession(id);
    this.messages.set([]);
    this.quickReplies.set([]);
    this.phase.set('ASK_DNI');
    this.currentStep.set(1);
    this.verification.set(null);
    this.wallet.set(null);
    this.durationMs.set(null);
    this.closed = false;
    this.retryAction = null;

    this.trace.log({ from: 'ui', to: 'api', kind: 'message', label: 'POST /chat/sessions', payload: { sessionId: id } });
    this.trace.track('onboarding_started');
    this.reply('Hola, soy tu asistente. Te ayudo a activar tu wallet en pocos pasos. Para empezar, escribe tu DNI (8 dígitos).');
  }

  private async route(text: string): Promise<void> {
    const normalized = normalize(text);
    if (RESTART.test(normalized)) {
      this.leave();
      return;
    }

    switch (this.phase()) {
      case 'ASK_DNI':
        return this.onDni(text);
      case 'PENDING_DECISION':
        return this.onDecision(normalized);
      case 'RETRY':
        return this.onRetry(normalized);
      case 'ACTIVE':
        return this.onActive(normalized);
      case 'REJECTED':
        this.reply('Tu registro no fue aprobado. Escribe «reiniciar» para intentarlo otra vez.', [QR_RESTART]);
    }
  }

  private async onDni(text: string): Promise<void> {
    const dni = text.replace(/[\s.-]/g, '');
    if (!/^\d{8}$/.test(dni)) {
      this.trace.log({
        from: 'api',
        to: 'api',
        kind: 'validation',
        status: 'error',
        label: 'Validación determinista: DNI inválido, se bloquea el avance',
        payload: { input: text, regla: '^\\d{8}$' },
      });
      this.reply('El DNI debe tener exactamente 8 números. Revisa que no falten ni sobren dígitos y escríbelo de nuevo.');
      return;
    }

    this.trace.log({
      from: 'api',
      to: 'api',
      kind: 'validation',
      label: 'Validación determinista: DNI válido',
      payload: { regla: '^\\d{8}$' },
    });
    await this.register(dni);
  }

  private async register(dni: string): Promise<void> {
    const args = { dni, scenario: this.scenario() };
    await this.llmDecide('El usuario entregó un DNI válido', 'create_kyc_verification', args);
    const created = await this.tools.createKycVerification(args);
    if (!created.ok) {
      this.fail(created, 'No pudimos registrar tu solicitud.', () => this.register(dni), [QR_RETRY, QR_FIX]);
      return;
    }

    this.verification.set(created.data);
    this.trace.track('step_completed', { step: 'registro' });
    this.currentStep.set(2);
    await this.refreshVerification(created.data.id);
  }

  private async refreshVerification(id: string): Promise<void> {
    await this.llmDecide('Confirmar el estado de la verificación', 'get_kyc_verification', { id });
    const checked = await this.tools.getKycVerification({ id });
    if (!checked.ok) {
      this.fail(checked, 'No pudimos consultar tu verificación.', () => this.refreshVerification(id), [QR_RETRY]);
      return;
    }
    await this.handleVerification(checked.data);
  }

  private async handleVerification(verification: KycVerification): Promise<void> {
    this.verification.set(verification);

    if (verification.status === 'ACTIVE') {
      this.trace.track('step_completed', { step: 'verificacion' });
      await this.openWallet(verification.wallet_id);
    } else if (verification.status === 'REJECTED') {
      this.trace.track('step_completed', { step: 'verificacion' });
      this.close('REJECTED');
      this.phase.set('REJECTED');
      this.reply('No pudimos activar tu wallet con los datos enviados. Puedes intentarlo de nuevo desde el inicio.', [QR_RESTART]);
    } else {
      this.phase.set('PENDING_DECISION');
      this.reply('Tu registro necesita una revisión manual antes de activarse. Resuélvela para continuar.', [
        QR_APPROVE,
        QR_REJECT,
        QR_FIX,
      ]);
    }
  }

  private async openWallet(walletId: string): Promise<void> {
    await this.llmDecide('Verificación aprobada, mostrar la wallet', 'get_wallet', { id: walletId });
    const result = await this.tools.getWallet({ id: walletId });
    if (!result.ok) {
      this.fail(result, 'No pudimos cargar tu wallet.', () => this.openWallet(walletId), [QR_RETRY]);
      return;
    }

    this.wallet.set(result.data);
    this.trace.track('step_completed', { step: 'wallet' });
    this.close('ACTIVE');
    this.currentStep.set(4);
    this.phase.set('ACTIVE');
    this.reply(
      `¡Listo! Tu wallet está activa. Saldo disponible: ${formatPEN(result.data.available)}. Ya puedes ir al punto de entrada de pagos de bajo monto.`,
      [QR_PAY, QR_RESTART],
    );
  }

  private async onDecision(normalized: string): Promise<void> {
    if (/corregir|dni|volver|atras/.test(normalized)) {
      this.askDni('Volvamos al registro. Escribe tu DNI de 8 dígitos.');
      return;
    }

    const decision = /aprob|acept|^si$/.test(normalized) ? 'ACTIVE' : /rechaz|^no$/.test(normalized) ? 'REJECTED' : null;
    const verification = this.verification();
    if (!decision || !verification) {
      this.reply('No entendí tu respuesta. Elige una opción para resolver la revisión.', [QR_APPROVE, QR_REJECT, QR_FIX]);
      return;
    }

    const args = { id: verification.id, decision } as const;
    await this.llmDecide(`El usuario resolvió la revisión: ${decision}`, 'decide_kyc_verification', args);
    const result = await this.tools.decideKycVerification(args);
    if (!result.ok) {
      if (result.status === 409) {
        await this.refreshVerification(verification.id);
        return;
      }
      this.fail(result, 'No se pudo registrar tu decisión.', () => this.onDecision(normalized), [QR_RETRY]);
      return;
    }
    await this.handleVerification(result.data);
  }

  private async onRetry(normalized: string): Promise<void> {
    if (/corregir|dni|volver|atras/.test(normalized)) {
      this.askDni('Volvamos al registro. Escribe tu DNI de 8 dígitos.');
    } else if (/reintent/.test(normalized) && this.retryAction) {
      const action = this.retryAction;
      this.retryAction = null;
      await action();
    } else {
      this.reply('Pulsa «Reintentar» para volver a intentarlo.', [QR_RETRY]);
    }
  }

  private async onActive(normalized: string): Promise<void> {
    if (/pag/.test(normalized)) {
      this.reply('El punto de entrada de pagos de bajo monto se habilitará en la siguiente etapa.', [QR_PAY, QR_RESTART]);
    } else {
      this.reply('Tu wallet ya está activa. Puedes ir a pagos o empezar de nuevo.', [QR_PAY, QR_RESTART]);
    }
  }

  private askDni(message: string): void {
    this.phase.set('ASK_DNI');
    this.currentStep.set(1);
    this.verification.set(null);
    this.retryAction = null;
    this.reply(message);
  }

  private fail(result: FailedResult, fallback: string, retry: () => Promise<void>, replies: QuickReply[]): void {
    this.retryAction = retry;
    this.phase.set('RETRY');
    this.reply(describeHttpError(result.error, fallback), replies);
  }

  private close(result: string): void {
    if (this.closed) {
      return;
    }
    this.closed = true;
    this.trace.track('onboarding_closed', { result });
    this.durationMs.set(Date.now() - this.trace.sessionStartedAt());
  }

  private async llmDecide(intent: string, tool: ToolName, args: unknown): Promise<void> {
    this.trace.log({
      from: 'api',
      to: 'llm',
      kind: 'decision',
      label: 'Prompt + tools MCP disponibles',
      payload: { intent, phase: this.phase(), tools: TOOL_DEFINITIONS.map((definition) => definition.name) },
    });
    await sleep(250);
    this.trace.log({ from: 'llm', to: 'api', kind: 'decision', label: `Decide usar ${tool}`, payload: { tool, args } });
  }

  private reply(text: string, quickReplies: QuickReply[] = []): void {
    this.pushMessage('agent', text);
    this.quickReplies.set(quickReplies);
    this.trace.log({
      from: 'api',
      to: 'ui',
      kind: 'message',
      label: 'Respuesta del agente',
      payload: {
        reply: text,
        currentStep: this.currentStep(),
        step: STEPS[this.currentStep() - 1],
        phase: this.phase(),
        quickReplies: quickReplies.map((quickReply) => quickReply.label),
      },
    });
  }

  private pushMessage(role: ChatMessage['role'], text: string): void {
    this.messages.update((messages) => [...messages, { id: ++this.msgSeq, role, text }]);
  }
}
