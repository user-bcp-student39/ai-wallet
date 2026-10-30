import { Component, inject } from '@angular/core';
import { ChatPanel } from './chat/chat-panel';
import { FlowDashboard } from './dashboard/flow-dashboard';
import { OnboardingAgent } from './core/onboarding-agent';
import { KycScenario } from './wallet-api.service';
import { SCENARIO_LABELS } from './shared/wallet-format';

@Component({
  selector: 'app-root',
  imports: [ChatPanel, FlowDashboard],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly agent = inject(OnboardingAgent);
  protected readonly scenarios = (Object.keys(SCENARIO_LABELS) as KycScenario[]).map((value) => ({
    value,
    label: SCENARIO_LABELS[value],
  }));
}
