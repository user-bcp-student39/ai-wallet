# Wallet frontend demo

Aplicación Angular 21 mobile-first para probar el contrato mock de KYC y wallet usando exclusivamente datos sintéticos.

El contrato OpenAPI está en [`services/api/openapi/wallet-mock.yaml`](../services/api/openapi/wallet-mock.yaml).

## Requisitos

- Node.js compatible con Angular 21 (Node.js 20.19+, 22.12+ o 24.x).
- El mock remoto está publicado en `https://bcp-wallet-mock.yefri.workers.dev`. Su contrato permite:
  - `POST /kyc/verifications`
  - `GET /kyc/verifications/{id}`
  - `POST /kyc/verifications/{id}/decision`
  - `GET /wallets/{id}`

## Ejecutar

Desde esta carpeta:

```powershell
npm start
```

Abre `http://localhost:4200`. `src/environments/environment.ts` configura Angular para llamar directamente a `https://bcp-wallet-mock.yefri.workers.dev`. El mock permite CORS desde el navegador.

## Validar

```powershell
npm test
npm run build
```

## Límite de la demo

La aplicación solicita únicamente identificadores ficticios `TEST-*`. KYC, aprobaciones y revisiones son simulados. No ingreses documentos reales. Esta app no integra la política KYC aprobada, persistencia productiva, analítica/atribución, pagos ni valores reales de MAU/CAC.
