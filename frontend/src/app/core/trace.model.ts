export type NodeId = 'ui' | 'agent' | 'graph' | 'analytics';

export type TraceKind =
  | 'message'
  | 'validation'
  | 'request'
  | 'run'
  | 'step'
  | 'interrupt'
  | 'state'
  | 'analytics';

export interface TraceEvent {
  id: number;
  at: number;
  from: NodeId;
  to: NodeId;
  kind: TraceKind;
  label: string;
  status: 'ok' | 'error';
  payload?: unknown;
  durationMs?: number;
}

export type AnalyticsEventName = 'onboarding_started' | 'step_completed' | 'onboarding_closed';

export interface AnalyticsEvent {
  id: number;
  at: number;
  name: AnalyticsEventName;
  sessionId: string;
  elapsedMs: number;
  step?: string;
  result?: string;
}

export interface NodeInfo {
  label: string;
  tech: string;
}

export const NODES: Record<NodeId, NodeInfo> = {
  ui: { label: 'Chat Angular', tech: 'frontend' },
  agent: { label: 'Endpoint AG-UI', tech: 'FastAPI · /agent' },
  graph: { label: 'Workflow LangGraph', tech: 'un nodo por paso' },
  analytics: { label: 'Analítica', tech: 'eventos MVP · en el cliente' },
};
