import { Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { KycScenario, WalletApiService } from '../wallet-api.service';
import { SCENARIO_LABELS, describeHttpError } from '../shared/wallet-format';
import { StepNav } from '../shared/step-nav';

const DNI_LENGTH = 8;

@Component({
  selector: 'app-registration-page',
  imports: [StepNav],
  templateUrl: './registration-page.html',
  styleUrl: '../shared/wallet-ui.scss',
})
export class RegistrationPage {
  private readonly api = inject(WalletApiService);
  private readonly router = inject(Router);

  readonly dniLength = DNI_LENGTH;
  readonly documentTypes = [{ value: 'DNI', label: 'DNI' }];
  readonly scenarios = (Object.keys(SCENARIO_LABELS) as KycScenario[]).map((value) => ({
    value,
    label: SCENARIO_LABELS[value],
  }));

  readonly dni = signal('');
  readonly scenario = signal<KycScenario>('APPROVED');
  readonly submitted = signal(false);
  readonly busy = signal(false);
  readonly errorMessage = signal('');

  readonly dniValid = computed(() => new RegExp(`^\\d{${DNI_LENGTH}}$`).test(this.dni()));
  readonly dniError = computed(() => {
    if (this.dni() === '') {
      return this.submitted() ? 'Ingresa tu número de DNI para continuar.' : '';
    }
    return this.dniValid() ? '' : `El DNI debe tener ${DNI_LENGTH} dígitos.`;
  });

  onDniInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    const digits = input.value.replace(/\D/g, '').slice(0, DNI_LENGTH);
    input.value = digits;
    this.dni.set(digits);
  }

  submit(event: Event): void {
    event.preventDefault();
    this.submitted.set(true);
    this.errorMessage.set('');
    if (!this.dniValid()) {
      return;
    }

    this.busy.set(true);
    // El mock solo acepta documentos de prueba (documentType TEST, prefijo TEST-).
    // El usuario ve y escribe su DNI; el prefijo se agrega aquí de forma interna.
    this.api
      .createVerification({
        documentType: 'TEST',
        document: `TEST-${this.dni()}`,
        scenario: this.scenario(),
      })
      .subscribe({
        next: (verification) => {
          this.router.navigate(['/verificacion', verification.id]);
        },
        error: (error: unknown) => {
          this.busy.set(false);
          this.errorMessage.set(describeHttpError(error, 'No se pudo completar el registro.'));
        },
      });
  }
}
