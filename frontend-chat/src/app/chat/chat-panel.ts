import { Component, ElementRef, effect, inject, signal, viewChild } from '@angular/core';
import { OnboardingAgent, STEPS } from '../core/onboarding-agent';

@Component({
  selector: 'app-chat-panel',
  templateUrl: './chat-panel.html',
  styleUrl: './chat-panel.scss',
})
export class ChatPanel {
  protected readonly agent = inject(OnboardingAgent);
  protected readonly steps = STEPS;
  protected readonly draft = signal('');

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
