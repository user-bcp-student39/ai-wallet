import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, firstValueFrom } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  KycScenario,
  KycVerification,
  VerificationDecision,
  Wallet,
  WalletApiService,
} from '../wallet-api.service';
import { ToolName } from './trace.model';
import { TraceStore } from './trace-store';

export type ToolResult<T> = { ok: true; data: T } | { ok: false; status: number; error: unknown };

interface HttpCall {
  method: 'GET' | 'POST';
  path: string;
  body?: unknown;
}

/**
 * Simula el servidor MCP: cada tool traduce una llamada del agente a un endpoint
 * real del mock y deja registrado cada salto en la traza.
 */
@Injectable({ providedIn: 'root' })
export class McpTools {
  private readonly api = inject(WalletApiService);
  private readonly trace = inject(TraceStore);
  private readonly baseUrl = environment.walletApiUrl.replace(/\/$/, '');

  createKycVerification(args: { dni: string; scenario: KycScenario }): Promise<ToolResult<KycVerification>> {
    // El prefijo TEST- lo exige el mock; el agente y el usuario solo manejan el DNI.
    const body = { documentType: 'TEST' as const, document: `TEST-${args.dni}`, scenario: args.scenario };
    return this.run('create_kyc_verification', args, { method: 'POST', path: '/kyc/verifications', body }, () =>
      this.api.createVerification(body),
    );
  }

  getKycVerification(args: { id: string }): Promise<ToolResult<KycVerification>> {
    return this.run(
      'get_kyc_verification',
      args,
      { method: 'GET', path: `/kyc/verifications/${args.id}` },
      () => this.api.getVerification(args.id),
    );
  }

  decideKycVerification(args: {
    id: string;
    decision: VerificationDecision;
  }): Promise<ToolResult<KycVerification>> {
    const body = { decision: args.decision };
    return this.run(
      'decide_kyc_verification',
      args,
      { method: 'POST', path: `/kyc/verifications/${args.id}/decision`, body },
      () => this.api.decideVerification(args.id, args.decision),
    );
  }

  getWallet(args: { id: string }): Promise<ToolResult<Wallet>> {
    return this.run('get_wallet', args, { method: 'GET', path: `/wallets/${args.id}` }, () =>
      this.api.getWallet(args.id),
    );
  }

  private async run<T>(
    tool: ToolName,
    args: unknown,
    http: HttpCall,
    execute: () => Observable<T>,
  ): Promise<ToolResult<T>> {
    const request = `${http.method} ${http.path}`;
    this.trace.log({ from: 'api', to: 'mcp', kind: 'tool-call', tool, label: `tools/call ${tool}`, payload: args });
    this.trace.log({
      from: 'mcp',
      to: 'mock',
      kind: 'http-request',
      tool,
      label: request,
      payload: { url: `${this.baseUrl}${http.path}`, body: http.body },
    });

    const startedAt = performance.now();
    try {
      const data = await firstValueFrom(execute());
      const durationMs = Math.round(performance.now() - startedAt);
      this.trace.log({ from: 'mock', to: 'mcp', kind: 'http-response', tool, label: `${request} → OK`, durationMs, payload: data });
      this.trace.log({ from: 'mcp', to: 'api', kind: 'tool-result', tool, label: `${tool} → resultado`, payload: data });
      return { ok: true, data };
    } catch (error) {
      const durationMs = Math.round(performance.now() - startedAt);
      const status = error instanceof HttpErrorResponse ? error.status : 0;
      const detail = error instanceof HttpErrorResponse ? (error.error ?? error.message) : String(error);
      this.trace.log({
        from: 'mock',
        to: 'mcp',
        kind: 'http-response',
        tool,
        status: 'error',
        durationMs,
        label: `${request} → ${status || 'sin respuesta'}`,
        payload: detail,
      });
      this.trace.log({
        from: 'mcp',
        to: 'api',
        kind: 'tool-result',
        tool,
        status: 'error',
        label: `${tool} → isError`,
        payload: { status },
      });
      return { ok: false, status, error };
    }
  }
}
