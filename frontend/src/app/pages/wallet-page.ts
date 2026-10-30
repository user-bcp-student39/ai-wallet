import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Wallet, WalletApiService } from '../wallet-api.service';
import { describeHttpError, formatPEN } from '../shared/wallet-format';
import { StepNav } from '../shared/step-nav';

@Component({
  selector: 'app-wallet-page',
  imports: [StepNav, RouterLink],
  templateUrl: './wallet-page.html',
  styleUrl: '../shared/wallet-ui.scss',
})
export class WalletPage implements OnInit {
  private readonly api = inject(WalletApiService);
  private readonly route = inject(ActivatedRoute);

  readonly walletId = this.route.snapshot.paramMap.get('id') ?? '';
  readonly wallet = signal<Wallet | null>(null);
  readonly loading = signal(true);
  readonly errorMessage = signal('');

  readonly formatPEN = formatPEN;

  ngOnInit(): void {
    this.api.getWallet(this.walletId).subscribe({
      next: (wallet) => {
        this.wallet.set(wallet);
        this.loading.set(false);
      },
      error: (error: unknown) => {
        this.loading.set(false);
        this.errorMessage.set(describeHttpError(error, 'No pudimos cargar tu wallet.'));
      },
    });
  }
}
