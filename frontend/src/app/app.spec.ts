import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { AGENT_FACTORY } from './core/onboarding-transport';

describe('App', () => {
  beforeEach(async () => {
    sessionStorage.clear();
    const idleAgent = {
      state: {},
      subscribe: () => ({ unsubscribe: () => undefined }),
      runAgent: () => new Promise(() => undefined),
    };
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [{ provide: AGENT_FACTORY, useValue: () => idleAgent }],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('muestra el chat y la trazabilidad', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('app-chat-panel h2')?.textContent).toContain('Activa tu wallet');
    expect(compiled.querySelector('app-flow-dashboard h2')?.textContent).toContain('Trazabilidad');
  });
});
