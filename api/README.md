# API — Central de Risco Climatico RS

Implementa `docs/API_CONTRACT.md` (v0). Le Parquet direto via DuckDB, nunca
carrega serie inteira em pandas quando da para consultar (§5.1 do contrato).
Fallback automatico real->sintetico em `api/deps.py`, mesmo espirito de
`app/data_source.py`: fonte ausente vira `basis: synthetic` ou `basis: null`
declarado, nunca 500 (§5.3).

## Subir

```bash
pip install fastapi uvicorn duckdb
uvicorn api.main:app --reload --port 8000
```

Docs interativas em `http://localhost:8000/docs`. CORS liberado so para
`http://localhost:5173` (Vite dev).

## Testes

```bash
python -m pytest tests/test_api.py -q
```

## Mapa endpoint -> pergunta que responde

| Endpoint | Pergunta |
|---|---|
| `GET /api/v1/meta` | Qual versao do contrato este backend fala? (o front confere no boot) |
| `GET /api/v1/state` | Onde o sistema climatico esta agora — ONI, taxa, blocos da Regua de Surpresa? |
| `GET /api/v1/state/ruler` | Os canais da Regua de Surpresa com trilha de 12 meses, prontos para o grafico |
| `GET /api/v1/series/{signal}` | Serie bruta de um sinal (`oni`, `sam`, `soi`, `nino34`, `satl`) num intervalo |
| `GET /api/v1/forecast/{season}` | Qual e a previsao de tercis para a estacao — e ela foi aceita ou a climatologia continua valendo? |
| `GET /api/v1/forecast/{season}/attribution` | Quanto cada bloco (ENSO, SAM, Atlantico Sul, tendencia) contribui, com contrafactual |
| `GET /api/v1/forecast/{season}/analogs` | Quais anos passados se parecem com o estado atual? |
| `GET /api/v1/risk/current` | Quais perigos estao ativos agora, e em que horizonte? |
| `GET /api/v1/risk/hazards` | Catalogo completo de perigos que a central cobre — E os que declaradamente NAO cobre (flash_flood) |
| `GET /api/v1/ledger` | Historico imutavel de previsoes emitidas vs observado |
| `GET /api/v1/ledger/skill` | RPSS/BSS/CRPS com IC — a engine tem skill de verdade? |
| `GET /api/v1/health/coverage` | Cobertura de dado por estacao x ano |
| `GET /api/v1/health/breaks` | Quebras de homogeneidade detectadas nas series de estacao |
| `GET /api/v1/health/sources` | Cada fonte (`cpc_oni`, `cpc_aao`, `cpc_soi`, `psl_nino`): quando foi ingerida pela ultima vez, hash, status |

## Estrutura

```
api/
  main.py              app FastAPI, CORS, prefixo /api/v1, /meta
  deps.py              acesso a dado (DuckDB + cache + fallback sintetico)
  models.py            schemas Pydantic v2 de toda resposta do contrato
  routers/
    state.py           /state, /state/ruler, /series/{signal}
    forecast.py         /forecast/{season}, .../attribution, .../analogs
    risk.py             /risk/current, /risk/hazards
    ledger.py           /ledger, /ledger/skill
    health.py           /health/coverage, /health/breaks, /health/sources
```

## Pontos onde o contrato foi ambiguo (resolvidos aqui, documentados)

1. **`/risk/current` vs `/risk/hazards`**: o contrato define ambos mas so
   detalha o payload de `hazards`. Implementei `/risk/hazards` como o
   catalogo completo (inclui itens com `level: null`, como `flash_flood` e
   `subseasonal_window`) e `/risk/current` como o subconjunto com nivel
   efetivamente elevado — a leitura que faz `current` ("o que esta ativo
   agora") semanticamente distinto de `hazards` ("o que a central cobre, e
   ate onde"). Se a intencao fosse outra (ex.: `current` tambem lista tudo,
   so que com `as_of`), e uma mudanca de poucas linhas em `risk.py`.

2. **`POST /risk/subscriptions`**: contrato lista mas anota "(Fase 9)" —
   nao implementado deliberadamente, e Fase 9 nao esta construida em lugar
   nenhum do repo (nem o M-SSA de regime, nem MJO). Implementar um POST sem
   persistencia real seria pior que nao ter a rota.

3. **`seasonal_dry_anomaly`**: nao esta no exemplo do contrato (so
   `seasonal_wet_anomaly` e `flash_flood` aparecem), mas o contrato diz
   "catalogo de perigos" no plural e a logica ENSO e simetrica (La Nina
   desloca para seco tanto quanto El Nino desloca para umido). Inclui-lo
   evita um catalogo que so sabe falar de excesso de chuva quando o sistema
   entrar em fase fria — se for indesejado, e remover um item da lista em
   `risk.py::_hazards_catalog`.

4. **Nivel de `seasonal_wet_anomaly`**: o contrato nao define a regra de
   negocio que mapeia ONI -> `low`/`elevated`/`high`. Usei os limiares
   operacionais do CPC (fraco/moderado/forte) ja usados em
   `src/state_report.py`, documentado em `risk.py::_seasonal_wet_level`. E
   um proxy razoavel, mas nao e o output de um modelo calibrado — a Camada 5
   (modelagem) ainda nao existe.
