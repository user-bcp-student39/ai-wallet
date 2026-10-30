import { Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { CopilotChat, injectAgentStore } from '@copilotkit/angular';

export interface OnboardingField {
  readonly name: string;
  readonly label: string;
  readonly type?: string;
}

export interface OnboardingStep {
  readonly step: number;
  readonly label: string;
  readonly fields: readonly OnboardingField[];
}

export const ONBOARDING_STEPS: readonly OnboardingStep[] = [
  {
    step: 1,
    label: 'Datos personales',
    fields: [
      { name: 'nombre', label: 'Nombre' },
      { name: 'apellidos', label: 'Apellidos' },
    ],
  },
  {
    step: 2,
    label: 'Contacto',
    fields: [
      { name: 'telefono', label: 'Teléfono' },
      { name: 'email', label: 'Email', type: 'email' },
    ],
  },
  {
    step: 3,
    label: 'Documento (DNI)',
    fields: [{ name: 'dni', label: 'DNI (8 dígitos)' }],
  },
  {
    step: 4,
    label: 'Monto máximo por operación',
    fields: [{ name: 'monto_maximo', label: 'Monto máximo en PEN (hasta 500)', type: 'number' }],
  },
  {
    step: 5,
    label: 'Activación',
    fields: [],
  },
];

export interface OnboardingError {
  readonly field: string | null;
  readonly message: string;
}

interface OnboardingPrompt {
  readonly step: number;
  readonly fields?: readonly string[];
  readonly errors?: readonly OnboardingError[];
}

interface OnboardingAgentState {
  readonly step?: number;
  readonly errors?: readonly OnboardingError[];
  readonly activated?: boolean;
  readonly done?: boolean;
}

const AGENT_ID = 'onboarding';
const THREAD_STORAGE_KEY = 'onboarding.threadId';

function loadThreadId(): string {
  const stored = sessionStorage.getItem(THREAD_STORAGE_KEY);
  if (stored) {
    return stored;
  }
  const threadId = crypto.randomUUID();
  sessionStorage.setItem(THREAD_STORAGE_KEY, threadId);
  return threadId;
}

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

@Component({
  selector: 'app-onboarding-chat',
  imports: [CopilotChat],
  templateUrl: './onboarding-chat.html',
  styleUrl: './onboarding-chat.css',
})
export class OnboardingChat {
  private readonly store = injectAgentStore(AGENT_ID);

  protected readonly threadId = loadThreadId();
  protected readonly steps = ONBOARDING_STEPS;
  protected readonly values = signal<Record<string, string>>({});
  private readonly prompt = signal<OnboardingPrompt | null>(null);
  private interruptId: string | undefined;

  protected readonly isRunning = computed(() => this.store().isRunning());
  protected readonly state = computed(
    () => (this.store().state() ?? {}) as OnboardingAgentState,
  );
  protected readonly currentStep = computed(() => this.prompt()?.step ?? this.state().step ?? 1);
  protected readonly activated = computed(() => this.state().activated === true);
  // El grafo terminó (`done`) sin activar: KYC no aprobada, API no disponible o fallo de registro.
  protected readonly failed = computed(() => this.state().done === true && !this.activated());
  protected readonly currentFields = computed(
    () => ONBOARDING_STEPS.find((s) => s.step === this.currentStep())?.fields ?? [],
  );
  protected readonly errors = computed(
    () => this.prompt()?.errors ?? this.state().errors ?? [],
  );
  protected readonly unassignedErrors = computed(() => {
    const names = new Set(this.currentFields().map((f) => f.name));
    return this.errors().filter((e) => !e.field || !names.has(e.field));
  });

  constructor() {
    const agent = this.store().agent;
    agent.threadId = this.threadId;
    const subscription = agent.subscribe({
      onCustomEvent: ({ event }) => {
        if (event.name !== 'on_interrupt') {
          return;
        }
        this.prompt.set(parsePrompt(event.value));
        this.interruptId = (event as { rawEvent?: { id?: string } }).rawEvent?.id;
      },
    });
    inject(DestroyRef).onDestroy(() => subscription.unsubscribe());
    untracked(() => {
      void agent.runAgent();
    });

    effect(() => {
      this.currentStep();
      untracked(() => this.values.set({}));
    });
  }

  protected fieldError(name: string): string | undefined {
    return this.errors().find((e) => e.field === name)?.message;
  }

  protected setValue(name: string, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.values.update((current) => ({ ...current, [name]: value }));
  }

  // Se envían todas las claves del paso: un payload vacío no llega al nodo del grafo.
  protected submitStep(event: Event): void {
    event.preventDefault();
    const current = this.values();
    const payload = Object.fromEntries(this.currentFields().map((f) => [f.name, current[f.name] ?? '']));
    this.resume(payload);
  }

  protected confirmActivation(): void {
    this.resume({ confirmar: true });
  }

  private resume(payload: Record<string, unknown>): void {
    void this.store()
      .agent.runAgent({
        resume: [{ interruptId: this.interruptId ?? '', status: 'resolved', payload }],
      })
      .catch((error: unknown) => console.error('[onboarding] resume failed', error));
  }
}
