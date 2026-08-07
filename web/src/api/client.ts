/**
 * Cliente HTTP fino, com dois modos.
 *
 * VIVO (dev e prod com backend): fala com `/api/v1` — proxy do Vite em dev,
 * mesmo host em prod.
 *
 * ESTATICO (`VITE_STATIC_API=1`, usado no build do GitHub Pages): nao ha
 * FastAPI do outro lado. Cada rota vira um arquivo JSON gerado em build por
 * `scripts/build_static_snapshot.py`, e `apiGet` passa a le-los. A demo
 * publica mostra a central completa em vez de uma casca carregando para
 * sempre.
 *
 * POR QUE nao usar um SDK gerado: o contrato (docs/API_CONTRACT.md) e a
 * fronteira estavel (ADR-014) — um cliente a mao contra o .md evita
 * acoplar o front a um schema OpenAPI que a API pode nem publicar ainda.
 */
const BASE = '/api/v1';

/** Ligado no build do Pages; falso em dev e em qualquer deploy com backend. */
export const MODO_ESTATICO = import.meta.env.VITE_STATIC_API === '1';

/** Raiz dos arquivos congelados. `BASE_URL` cobre o subcaminho do Pages. */
const RAIZ_ESTATICA = `${import.meta.env.BASE_URL}static-api`;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Chave de arquivo para (rota, parametros).
 *
 * ESTA FUNCAO TEM UMA GEMEA em `scripts/build_static_snapshot.py`. As duas
 * precisam concordar caractere a caractere: se divergirem, o front pede um
 * arquivo que o build nao gerou e a demo quebra so em producao — o pior lugar
 * para descobrir. `tests/test_static_snapshot.py` compara as duas.
 */
export function slugEstatico(path: string, params?: Record<string, string | undefined>): string {
  let base = path.replace(/^\//, '').replace(/\//g, '_');
  if (params) {
    for (const chave of Object.keys(params).sort()) {
      const valor = params[chave];
      if (valor === undefined) continue;
      base += `~${chave}-${String(valor).replace(/[^A-Za-z0-9]+/g, '-')}`;
    }
  }
  return base;
}

/**
 * URL de um asset binario servido pela API (hoje so o overlay de agua).
 * Em modo estatico aponta para o arquivo copiado no snapshot.
 */
export function assetUrl(path: string): string {
  return MODO_ESTATICO ? `${RAIZ_ESTATICA}/${slugEstatico(path)}` : `${BASE}${path}`;
}

export async function apiGet<T>(path: string, params?: Record<string, string | undefined>): Promise<T> {
  if (MODO_ESTATICO) {
    const url = `${RAIZ_ESTATICA}/${slugEstatico(path, params)}.json`;
    const res = await fetch(url);
    if (!res.ok) {
      // Mensagem nomeia o arquivo faltando, nao so a rota: em modo estatico o
      // erro quase sempre e "o snapshot nao cobriu este parametro", e saber o
      // nome esperado resolve em um passo.
      throw new ApiError(res.status, `snapshot ausente: ${url} (rota ${path})`);
    }
    return res.json() as Promise<T>;
  }

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
