import { Component, ElementRef, computed, effect, inject, signal, viewChild } from '@angular/core';
import { FIELDS } from '../core/onboarding.model';
import { OnboardingAgent, Phase, STEPS } from '../core/onboarding-agent';

const STATUS_BADGES: Partial<Record<Phase, { label: string; tone: 'ok' | 'warn' | 'error' }>> = {
  ACTIVE: { label: 'Wallet activa', tone: 'ok' },
  REJECTED: { label: 'KYC rechazada', tone: 'error' },
  PENDING: { label: 'Revisión pendiente', tone: 'warn' },
  UNAVAILABLE: { label: 'Servicio no disponible', tone: 'warn' },
  FAILED: { label: 'Activación fallida', tone: 'error' },
  RETRY: { label: 'Sin conexión', tone: 'warn' },
};

@Component({
  selector: 'app-chat-panel',
  templateUrl: './chat-panel.html',
  styleUrl: './chat-panel.scss',
})
export class ChatPanel {
  protected readonly agent = inject(OnboardingAgent);
  protected readonly steps = STEPS;
  protected readonly draft = signal('');

  protected readonly status = computed(() => STATUS_BADGES[this.agent.phase()] ?? null);
  protected readonly inputMode = computed(() => FIELDS[this.agent.currentField() ?? '']?.inputMode ?? 'text');
  protected readonly placeholder = computed(() => {
    const field = FIELDS[this.agent.currentField() ?? ''];
    if (field) {
      return `Escribe tu ${field.label}`;
    }
    return this.agent.phase() === 'CONFIRM' ? 'Escribe «activar» para confirmar' : 'Escribe tu respuesta…';
  });

  private readonly list = viewChild<ElementRef<HTMLElement>>('list');

  constructor() {
    effect(() => {
      this.agent.messages();
      this.agent.busy();
      const element = this.list()?.nativeElement;
      if (element) {
        setTimeout(() => (element.scrollTop = element.scrollHeight));
      }
    });
  }

  protected onInput(event: Event): void {
    this.draft.set((event.target as HTMLInputElement).value);
  }

  protected submit(event: Event): void {
    event.preventDefault();
    const text = this.draft();
    this.draft.set('');
    void this.agent.send(text);
  }

  protected quickReply(text: string): void {
    void this.agent.send(text);
  }
}
