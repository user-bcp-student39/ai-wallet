import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideCopilotKit } from '@copilotkit/angular';
import { HttpAgent } from '@ag-ui/client';
import { routes } from './app.routes';

const ONBOARDING_AGENT_URL = 'http://localhost:8000/agent';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideCopilotKit({
      agents: { onboarding: new HttpAgent({ url: ONBOARDING_AGENT_URL }) },
    }),
  ],
};
