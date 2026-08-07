/**
 * Regra critica do brief: FRIO (#3E7FA8) e QUENTE (#C1553A) sao exclusivas
 * do dado. Este teste faz grep em todo `src/` por esses dois hex e falha se
 * aparecerem fora de modulos de grafico — definidos aqui como:
 *   - arquivos dentro de `src/theme/` (onde os hex sao a fonte da verdade)
 *   - arquivos que IMPORTAM de `theme/chartColors` (isto e, consomem a cor
 *     apenas para desenhar dado, nao para decorar UI) — na pratica,
 *     qualquer arquivo que importe chartColors e onde os hex podem aparecer
 *     (via a propria importacao, nao hardcoded) e permitido; hex hardcoded
 *     fora de theme/ e sempre proibido, mesmo em componente de grafico —
 *     o grafico deve importar a constante, nunca reescrever o valor.
 */
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const SRC = resolve(__dirname, '../../');
const FORBIDDEN = ['#3E7FA8', '#C1553A'];
const ALLOWED_DIR = resolve(SRC, 'theme'); // unico lugar onde os hex podem ser escritos

function listFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      if (entry === 'node_modules') continue;
      out.push(...listFiles(full));
    } else if (/\.(ts|tsx|css)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

describe('regra da paleta — FRIO/QUENTE exclusivas do dado', () => {
  it('nenhum arquivo fora de src/theme/ contem os hex de FRIO ou QUENTE', () => {
    const offenders: string[] = [];
    for (const file of listFiles(SRC)) {
      if (file.startsWith(ALLOWED_DIR)) continue; // theme/ e a fonte da verdade
      const content = readFileSync(file, 'utf-8');
      for (const hex of FORBIDDEN) {
        if (content.toUpperCase().includes(hex.toUpperCase())) {
          offenders.push(`${file} contem ${hex}`);
        }
      }
    }
    expect(offenders, offenders.join('\n')).toEqual([]);
  });
});
