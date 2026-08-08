import { http, HttpResponse } from 'msw';
import * as fx from './fixtures';

const BASE = '/api/v1';

export const handlers = [
  http.get(`${BASE}/meta`, () => HttpResponse.json(fx.metaFixture)),
  http.get(`${BASE}/state`, () => HttpResponse.json(fx.stateFixture)),
  http.get(`${BASE}/state/ruler`, () => HttpResponse.json(fx.rulerFixture)),
  http.get(`${BASE}/series/:signal`, () => HttpResponse.json(fx.seriesOniFixture)),
  http.get(`${BASE}/forecast/:season/attribution`, () => HttpResponse.json(fx.attributionFixture)),
  http.get(`${BASE}/forecast/:season/analogs`, () => HttpResponse.json(fx.analogsFixture)),
  http.get(`${BASE}/forecast/:season`, () => HttpResponse.json(fx.forecastNotAcceptedFixture)),
  http.get(`${BASE}/risk/current`, () => HttpResponse.json(fx.riskFixture)),
  // Catalogo completo: a tela de risco consome ESTE, nao `current`.
  http.get(`${BASE}/risk/hazards`, () => HttpResponse.json(fx.riskFixture)),
  http.get(`${BASE}/ledger/skill`, () => HttpResponse.json(fx.ledgerSkillFixture)),
  http.get(`${BASE}/ledger`, () => HttpResponse.json(fx.ledgerFixture)),
  http.get(`${BASE}/health/coverage`, () => HttpResponse.json(fx.coverageFixture)),
  http.get(`${BASE}/health/breaks`, () => HttpResponse.json(fx.breaksFixture)),
  http.get(`${BASE}/health/sources`, () => HttpResponse.json(fx.sourcesFixture)),
  http.get(`${BASE}/references`, () => HttpResponse.json(fx.referencesFixture)),

  // --- rotas do dominio municipal ---------------------------------------
  // A tela principal passou a consumir estas quatro. Sem handler, o MSW
  // grita "intercepted a request without a matching request handler" e o
  // teste falha por rede, nao por regressao — ruido que esconde o defeito
  // real. Fixtures MINIMAS de proposito: o teste da tela principal verifica
  // o card de flash_flood, nao o conteudo do plano.
  http.get(`${BASE}/risk/municipal`, () => HttpResponse.json(fx.municipalFixture)),
  http.get(`${BASE}/geo/municipios`, () => HttpResponse.json(fx.malhaFixture)),
  http.get(`${BASE}/plano`, () => HttpResponse.json(fx.planoFixture)),
  http.get(`${BASE}/outlook/enso`, () => HttpResponse.json(fx.outlookFixture)),
];
