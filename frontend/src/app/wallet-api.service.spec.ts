import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { WalletApiService } from './wallet-api.service';
import { environment } from '../environments/environment';

const walletApiUrl = environment.walletApiUrl;

describe('WalletApiService', () => {
  let api: WalletApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(WalletApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('creates a synthetic KYC verification', () => {
    api.createVerification({
      documentType: 'TEST',
      document: 'TEST-001',
      scenario: 'MANUAL_REVIEW',
    }).subscribe();

    const request = http.expectOne(`${walletApiUrl}/kyc/verifications`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      documentType: 'TEST',
      document: 'TEST-001',
      scenario: 'MANUAL_REVIEW',
    });
    request.flush({ id: 'kyc-1', wallet_id: 'wallet-1', scenario: 'MANUAL_REVIEW', status: 'PENDING' });
  });

  it('queries a KYC verification by id', () => {
    api.getVerification('kyc-1').subscribe();

    const request = http.expectOne(`${walletApiUrl}/kyc/verifications/kyc-1`);
    expect(request.request.method).toBe('GET');
    request.flush({ id: 'kyc-1', wallet_id: 'wallet-1', scenario: 'APPROVED', status: 'ACTIVE' });
  });

  it('posts the selected human-review demo decision', () => {
    api.decideVerification('kyc-1', 'REJECTED').subscribe();

    const request = http.expectOne(`${walletApiUrl}/kyc/verifications/kyc-1/decision`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ decision: 'REJECTED' });
    request.flush({ id: 'kyc-1', wallet_id: 'wallet-1', scenario: 'MANUAL_REVIEW', status: 'REJECTED' });
  });

  it('queries wallet balances by wallet id', () => {
    api.getWallet('wallet-1').subscribe();

    const request = http.expectOne(`${walletApiUrl}/wallets/wallet-1`);
    expect(request.request.method).toBe('GET');
    request.flush({
      id: 'wallet-1',
      status: 'ACTIVE',
      balance: 100000,
      reserved: 0,
      available: 100000,
      currency: 'PEN',
    });
  });
});
