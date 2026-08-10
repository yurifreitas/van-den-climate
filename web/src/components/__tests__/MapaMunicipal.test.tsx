import { describe, expect, it } from 'vitest';
import { render } from '@testing-library/react';
import { MapaMunicipal, TETO_PONTOS, pontosDesenhados } from '../MapaMunicipal';
import type { MalhaResponse } from '../../api/types';

/**
 * Regressao da tela de recursos que travava o navegador (2026-08-09).
 *
 * Cada ponto rendia DOIS nos de DOM — um `<circle>` e um `<title>` filho. Com a
 * familia de socorro sozinha eram ~3,2 mil nos e ninguem notava; ligando as
 * outras quatro, os 18,7 mil pontos viravam ~37 mil nos. E como `hover` e
 * estado do proprio mapa, cada movimento do mouse re-renderizava a arvore
 * inteira: passar o mouse algumas vezes derrubava o renderizador e a aba
 * ficava em branco.
 *
 * O teste nao mede tempo — medida de tempo em CI e ruido. Ele trava o que
 * causou o problema: quantos NOS o mapa cria para um conjunto grande de
 * pontos, e se o teto e declarado em vez de silencioso.
 */
const malha: MalhaResponse = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { codarea: '4314902' },
      geometry: {
        type: 'Polygon',
        coordinates: [[[-52, -31], [-51, -31], [-51, -30], [-52, -30], [-52, -31]]],
      },
    },
  ],
} as unknown as MalhaResponse;

function pontos(n: number) {
  return Array.from({ length: n }, (_, i) => ({
    lon: -52 + (i % 100) / 100,
    lat: -31 + (i % 97) / 97,
    papel: 'abrigo_escola',
    nome: `ponto ${i}`,
  }));
}

describe('MapaMunicipal com muitos pontos', () => {
  it('respeita o teto de pontos desenhados', () => {
    const { container } = render(
      <MapaMunicipal
        malha={malha}
        municipios={[]}
        camada="recursos"
        selecionado={null}
        onSelecionar={() => {}}
        recursos={pontos(20000)}
        coresRecurso={{ abrigo_escola: '#fff' }}
      />,
    );
    const circulos = container.querySelectorAll('circle').length;
    expect(circulos).toBeGreaterThan(0);
    expect(circulos).toBeLessThanOrEqual(TETO_PONTOS);
  });

  it('nao cria um <title> por ponto — era metade dos nos', () => {
    const { container } = render(
      <MapaMunicipal
        malha={malha}
        municipios={[]}
        camada="recursos"
        selecionado={null}
        onSelecionar={() => {}}
        recursos={pontos(5000)}
        coresRecurso={{ abrigo_escola: '#fff' }}
      />,
    );
    // Um <title> por poligono continua valendo: sao 497 no estado inteiro.
    expect(container.querySelectorAll('title').length).toBeLessThan(600);
  });

  it('abaixo do teto desenha todos, sem amostrar', () => {
    expect(pontosDesenhados(1621)).toBe(1621);
    expect(pontosDesenhados(TETO_PONTOS)).toBe(TETO_PONTOS);
  });

  it('acima do teto, o descarte e calculavel por quem chama', () => {
    const desenhados = pontosDesenhados(18688);
    expect(desenhados).toBeLessThanOrEqual(TETO_PONTOS);
    expect(desenhados).toBeGreaterThan(TETO_PONTOS / 2);
  });
});
