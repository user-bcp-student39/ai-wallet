import { Component } from '@angular/core';
import { OnboardingChat } from './onboarding/onboarding-chat';

@Component({
  imports: [OnboardingChat],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App {}
