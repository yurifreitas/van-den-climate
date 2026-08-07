/**
 * Cliente HTTP fino. Base `/api/v1` funciona tanto em dev (proxy do
 * vite.config.ts para localhost:8000) quanto em prod atras do mesmo host.
 *
 * POR QUE nao usar um SDK gerado: o contrato (docs/API_CONTRACT.md) e a
 * fronteira estavel (ADR-014) — um cliente a mao contra o .md evita
 * acoplar o front a um schema OpenAPI que a API pode nem publicar ainda.
 */
const BASE = '/api/v1';

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiGet<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString().replace(window.location.origin, ''));
  if (!res.ok) {
    throw new ApiError(res.status, `GET ${path} -> ${res.status}`);
  }
  return res.json() as Promise<T>;
}
