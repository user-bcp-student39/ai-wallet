import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { KycVerification, VerificationDecision, WalletApiService } from '../wallet-api.service';
import { SCENARIO_LABELS, describeHttpError } from '../shared/wallet-format';
import { StepNav } from '../shared/step-nav';

@Component({
  selector: 'app-verification-page',
  imports: [StepNav, RouterLink],
  templateUrl: './verification-page.html',
  styleUrl: '../shared/wallet-ui.scss',
})
export class VerificationPage implements OnInit {
  private readonly api = inject(WalletApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly verificationId = this.route.snapshot.paramMap.get('id') ?? '';

  readonly verification = signal<KycVerification | null>(null);
  readonly busy = signal(false);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly scenarioLabel = computed(() => {
    const current = this.verification();
    return current ? SCENARIO_LABELS[current.scenario] : '';
  });

  ngOnInit(): void {
    this.api.getVerification(this.verificationId).subscribe({
      next: (verification) => this.handleVerification(verification),
      error: (error: unknown) => this.fail(error, 'No pudimos consultar tu verificación.'),
    });
  }

  decide(decision: VerificationDecision): void {
    this.busy.set(true);
    this.errorMessage.set('');
    this.api.decideVerification(this.verificationId, decision).subscribe({
      next: (verification) => this.handleVerification(verification),
      error: (error: unknown) => this.fail(error, 'No se pudo registrar tu decisión.'),
    });
  }

  private handleVerification(verification: KycVerification): void {
    this.verification.set(verification);
    this.loading.set(false);
    this.busy.set(false);

    // Flujo automático: si la wallet ya está activa, pasamos a la pantalla de wallet.
    if (verification.status === 'ACTIVE') {
      this.router.navigate(['/wallet', verification.wallet_id]);
    }
  }

  private fail(error: unknown, fallback: string): void {
    this.loading.set(false);
    this.busy.set(false);
    this.errorMessage.set(describeHttpError(error, fallback));
  }
}
