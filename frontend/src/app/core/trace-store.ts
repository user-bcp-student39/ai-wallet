import { Injectable, signal } from '@angular/core';
import { AnalyticsEvent, AnalyticsEventName, TraceEvent } from './trace.model';

@Injectable({ providedIn: 'root' })
export class TraceStore {
  private seq = 0;

  readonly events = signal<TraceEvent[]>([]);
  readonly analytics = signal<AnalyticsEvent[]>([]);
  readonly sessionStartedAt = signal(Date.now());
  readonly sessionId = signal('');

  log(event: Omit<TraceEvent, 'id' | 'at' | 'status'> & { status?: TraceEvent['status'] }): void {
    const entry: TraceEvent = { id: ++this.seq, at: Date.now(), status: 'ok', ...event };
    this.events.update((events) => [...events, entry]);
  }

  track(name: AnalyticsEventName, extra: { step?: string; result?: string } = {}): void {
    const now = Date.now();
    const entry: AnalyticsEvent = {
      id: ++this.seq,
      at: now,
      name,
      sessionId: this.sessionId(),
      elapsedMs: now - this.sessionStartedAt(),
      ...extra,
    };
    this.analytics.update((events) => [...events, entry]);
    this.log({ from: 'ui', to: 'analytics', kind: 'analytics', label: name, payload: entry });
  }

  beginSession(sessionId: string): void {
    this.sessionId.set(sessionId);
    this.sessionStartedAt.set(Date.now());
  }

  clear(): void {
    this.events.set([]);
    this.analytics.set([]);
  }
}
