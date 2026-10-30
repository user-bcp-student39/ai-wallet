import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { routes } from './app.routes';
import { environment } from '../environments/environment';

const base = environment.walletApiUrl.replace(/\/$/, '');

describe('Flujo de registro', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function typeDni(harness: RouterTestingHarness, value: string): HTMLInputElement {
    const input = harness.routeNativeElement!.querySelector<HTMLInputElement>('#dni')!;
    input.value = value;
    input.dispatchEvent(new Event('input'));
    harness.fixture.detectChanges();
    return input;
  }

  it('ofrece solo DNI y acepta únicamente 8 dígitos', async () => {
    const harness = await RouterTestingHarness.create('/registro');
    const select = harness.routeNativeElement!.querySelector<HTMLSelectElement>('#document-type')!;
    expect(Array.from(select.options).map((o) => o.value)).toEqual(['DNI']);

    const input = typeDni(harness, '12ab345678901');
    expect(input.value).toBe('12345678');
  });

  it('bloquea el envío con menos de 8 dígitos sin llamar al servicio', async () => {
    const harness = await RouterTestingHarness.create('/registro');
    typeDni(harness, '1234');

    harness.routeNativeElement!.querySelector<HTMLFormElement>('form')!.requestSubmit();
    harness.fixture.detectChanges();

    expect(harness.routeNativeElement!.textContent).toContain('El DNI debe tener 8 dígitos.');
  });

  it('continúa automáticamente hasta la wallet activa', async () => {
    const harness = await RouterTestingHarness.create('/registro');
    typeDni(harness, '12345678');
    harness.routeNativeElement!.querySelector<HTMLFormElement>('form')!.requestSubmit();

    const create = http.expectOne(`${base}/kyc/verifications`);
    expect(create.request.body).toEqual({
      documentType: 'TEST',
      document: 'TEST-12345678',
      scenario: 'APPROVED',
    });
    create.flush({ id: 'kyc_1', wallet_id: 'wallet_1', scenario: 'APPROVED', status: 'ACTIVE' });
    await harness.fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/verificacion/kyc_1');
    http
      .expectOne(`${base}/kyc/verifications/kyc_1`)
      .flush({ id: 'kyc_1', wallet_id: 'wallet_1', scenario: 'APPROVED', status: 'ACTIVE' });
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();

    http.expectOne(`${base}/wallets/wallet_1`).flush({
      id: 'wallet_1',
      status: 'ACTIVE',
      balance: 0,
      reserved: 0,
      available: 0,
      currency: 'PEN',
    });
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();

    expect(harness.routeNativeElement!.textContent).toContain('Disponible');
    const pay = harness.routeNativeElement!.querySelector<HTMLButtonElement>('.payment-entry button')!;
    expect(pay.disabled).toBe(true);
  });
});
