import { Component } from '@angular/core';
import { ChatPanel } from './chat/chat-panel';
import { FlowDashboard } from './dashboard/flow-dashboard';

@Component({
  selector: 'app-root',
  imports: [ChatPanel, FlowDashboard],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
