import { Component, input } from '@angular/core';

@Component({
  selector: 'app-step-nav',
  template: `
    <nav class="step-nav" aria-label="Pasos del registro">
      <ol>
        @for (step of steps; track step.number) {
          <li [class.is-current]="step.number === current()"
              [class.is-complete]="step.number < current()"
              [attr.aria-current]="step.number === current() ? 'step' : null">
            <span class="step-number">{{ step.number }}</span><span>{{ step.label }}</span>
          </li>
        }
      </ol>
      <p class="step-caption">Paso {{ current() }} de {{ steps.length }}</p>
    </nav>
  `,
  styleUrl: './wallet-ui.scss',
})
export class StepNav {
  readonly current = input.required<number>();
  readonly steps = [
    { number: 1, label: 'Registro' },
    { number: 2, label: 'Verificación' },
    { number: 3, label: 'Wallet' },
    { number: 4, label: 'Pagos' },
  ];
}
