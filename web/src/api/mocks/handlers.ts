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
];
