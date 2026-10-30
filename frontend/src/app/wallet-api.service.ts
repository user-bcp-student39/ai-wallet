import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../environments/environment';

export type KycScenario = 'APPROVED' | 'REJECTED' | 'MANUAL_REVIEW' | 'UNAVAILABLE';
export type KycStatus = 'ACTIVE' | 'PENDING' | 'REJECTED';
export type WalletStatus = KycStatus;
export type VerificationDecision = 'ACTIVE' | 'REJECTED';

export interface CreateVerificationRequest {
  documentType: 'TEST';
  document: string;
  scenario: KycScenario;
}

export interface KycVerification {
  id: string;
  wallet_id: string;
  scenario: Exclude<KycScenario, 'UNAVAILABLE'>;
  status: KycStatus;
}

export interface Wallet {
  id: string;
  status: WalletStatus;
  balance: number;
  reserved: number;
  available: number;
  currency: 'PEN';
}

@Injectable({ providedIn: 'root' })
export class WalletApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.walletApiUrl.replace(/\/$/, '');

  createVerification(request: CreateVerificationRequest): Observable<KycVerification> {
    return this.http.post<KycVerification>(`${this.baseUrl}/kyc/verifications`, request);
  }

  getVerification(id: string): Observable<KycVerification> {
    return this.http.get<KycVerification>(
      `${this.baseUrl}/kyc/verifications/${encodeURIComponent(id)}`,
    );
  }

  decideVerification(id: string, decision: VerificationDecision): Observable<KycVerification> {
    return this.http.post<KycVerification>(
      `${this.baseUrl}/kyc/verifications/${encodeURIComponent(id)}/decision`,
      { decision },
    );
  }

  getWallet(id: string): Observable<Wallet> {
    return this.http.get<Wallet>(`${this.baseUrl}/wallets/${encodeURIComponent(id)}`);
  }
}
