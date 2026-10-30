export type NodeId = 'ui' | 'api' | 'llm' | 'mcp' | 'mock' | 'analytics';

export type TraceKind =
  | 'message'
  | 'validation'
  | 'decision'
  | 'tool-call'
  | 'http-request'
  | 'http-response'
  | 'tool-result'
  | 'analytics';

export type ToolName =
  | 'create_kyc_verification'
  | 'get_kyc_verification'
  | 'decide_kyc_verification'
  | 'get_wallet';

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
  tool?: ToolName;
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
  real: boolean;
}

export const NODES: Record<NodeId, NodeInfo> = {
  ui: { label: 'Chat Angular', tech: 'frontend-chat', real: true },
  api: { label: 'API Java', tech: 'Spring Boot · simulada', real: false },
  llm: { label: 'Agente LLM', tech: 'decisión simulada', real: false },
  mcp: { label: 'Servidor MCP', tech: '4 tools · simulado', real: false },
  mock: { label: 'Mock KYC y wallet', tech: 'Cloudflare Worker', real: true },
  analytics: { label: 'Analítica', tech: 'eventos MVP · simulada', real: false },
};

export interface ToolDefinition {
  name: ToolName;
  method: 'GET' | 'POST';
  path: string;
  description: string;
}

export const TOOL_DEFINITIONS: ToolDefinition[] = [
  {
    name: 'create_kyc_verification',
    method: 'POST',
    path: '/kyc/verifications',
    description: 'Registra al usuario con su DNI. Arma internamente el documento TEST-<dni>.',
  },
  {
    name: 'get_kyc_verification',
    method: 'GET',
    path: '/kyc/verifications/{id}',
    description: 'Consulta el estado de la verificación.',
  },
  {
    name: 'decide_kyc_verification',
    method: 'POST',
    path: '/kyc/verifications/{id}/decision',
    description: 'Resuelve una verificación en revisión manual.',
  },
  {
    name: 'get_wallet',
    method: 'GET',
    path: '/wallets/{id}',
    description: 'Consulta el estado y los saldos de la wallet.',
  },
];
