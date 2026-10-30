import { Component, computed, inject } from '@angular/core';
import { NODES, TraceKind } from '../core/trace.model';
import { TraceStore } from '../core/trace-store';

const KIND_LABELS: Record<TraceKind, string> = {
  message: 'mensaje',
  validation: 'validación',
  request: 'HTTP ida',
  run: 'ejecución AG-UI',
  step: 'nodo del grafo',
  interrupt: 'interrupt',
  state: 'estado',
  analytics: 'analítica',
};

@Component({
  selector: 'app-flow-dashboard',
  templateUrl: './flow-dashboard.html',
  styleUrl: './flow-dashboard.scss',
})
export class FlowDashboard {
  protected readonly store = inject(TraceStore);
  protected readonly nodes = NODES;

  protected readonly timeline = computed(() => [...this.store.events()].reverse());

  protected kindLabel(kind: TraceKind): string {
    return KIND_LABELS[kind];
  }

  protected offset(at: number): string {
    const first = this.store.events()[0]?.at ?? at;
    return `+${((at - first) / 1000).toFixed(2)} s`;
  }

  protected json(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }
}
