# Contrato de API — Central de Risco RS

**Status**: v0, congelado como fronteira entre back e front (ADR-014).
Front e pipeline evoluem em paralelo *porque* este contrato absorve mudanças de
esquema. Se um endpoint expuser detalhe de armazenamento (nome de parquet,
`signal_id` interno, coluna de ingestão), o acoplamento volta e o pivô perde
sentido.

Base: `/api/v1`. Tudo JSON. Datas ISO-8601. Sem estado de sessão.

---

## 0. O invariante que atravessa todo endpoint

Toda resposta que contenha número derivado carrega **proveniência epistêmica**:

```json
"provenance": {
  "basis": "measured" | "modeled" | "synthetic",
  "horizon": "seasonal" | "subseasonal" | "synoptic",
  "source_ids": ["cpc_oni"],
  "as_of": "2026-08-07T12:33:47Z",
  "n_effective": 36
}
```

`basis` é a fronteira medido/prior tornada máquina-legível. O front **deve**
renderizá-la; um número sem selo é bug de interface, não escolha de design.

`horizon` existe por causa da central de risco: a engine sazonal desloca
probabilidade de fundo e não prevê eventos individuais. Um endpoint nunca
devolve `"horizon": "synoptic"` — não há camada que o sustente, e a ausência
precisa ser explícita, não silenciosa.

---

## 1. Estado

```
GET /state                          → estado atual de todos os blocos
GET /state/ruler                    → Régua de Surpresa (canais + trilha 12m)
GET /series/{signal}?from=&to=       → série temporal (signal: oni|sam|soi|nino34|satl)
```

`GET /state` →
```json
{
  "as_of": "2026-06-01",
  "headline": {"oni": 1.39, "classification": "El Nino moderado",
               "rate_per_season": 0.43},
  "blocks": [
    {"id": "enso_state", "label": "Estado ENSO", "percentile": 0.94,
     "value": 1.39, "trail_12m": [0.21, 0.28, ...],
     "provenance": {"basis": "measured", "horizon": "seasonal", ...}}
  ]
}
```

`percentile` é o percentil **causal** (resolução 1/t). Quando `t < 30` a
resposta inclui `"resolution_warning": true` — o front mostra o número
esmaecido. Fingir precisão que a amostra não tem é o erro que a engine inteira
existe para não cometer.

---

## 2. Previsão

```
GET /forecast/{season}              → trio de alvos, tercis, vs climatologia
GET /forecast/{season}/attribution  → contribuição por bloco + contrafactual
GET /forecast/{season}/analogs      → anos análogos ranqueados
```

```json
{
  "season": "OND2026",
  "issued_at": null,
  "status": "not_accepted",
  "acceptance": {"criterion": "lower bound of 90% CI of RPSS > 0",
                 "rpss": {"point": null, "lo": null, "hi": null},
                 "verdict": "climatology remains in force"},
  "targets": [
    {"id": "wetday_freq", "label": "Frequencia de dias umidos",
     "terciles": {"below": 0.33, "normal": 0.33, "above": 0.34},
     "climatology": {"below": 0.33, "normal": 0.33, "above": 0.33},
     "provenance": {"basis": "measured", "horizon": "seasonal"}}
  ]
}
```

`status: "not_accepted"` com a climatologia vigente é o estado **correto** hoje,
não um erro a ser escondido. O front mostra isso como resultado, não como vazio.

---

## 3. Risco (novo — a camada que o pivô introduz)

```
GET  /risk/current                  → perigos ativos, por horizonte
GET  /risk/hazards                  → catálogo de perigos e o que os sustenta
POST /risk/subscriptions            → alerta por limiar (Fase 9)
```

```json
{
  "hazards": [
    {"id": "seasonal_wet_anomaly", "label": "Excesso de chuva sazonal OND",
     "level": "elevated", "horizon": "seasonal",
     "basis": "measured",
     "drivers": ["enso_state"],
     "limits": "Desloca probabilidade de fundo. NAO indica evento individual."},
    {"id": "flash_flood", "label": "Cheia rapida",
     "level": null, "horizon": "synoptic",
     "basis": null,
     "limits": "Fora do escopo desta engine — exige modelo dinamico. Consulte
                Defesa Civil / SEMA-RS Sala de Situacao."}
  ]
}
```

O perigo sinótico aparece no catálogo **com `level: null` e o encaminhamento
externo**. Omiti-lo faria a central parecer completa; declará-lo vazio é o que
impede alguém de assumir cobertura que não existe. Essa é a decisão de produto
mais importante do pivô.

---

## 4. Ledger e saúde

```
GET /ledger?target=&from=&to=       → previsoes emitidas vs observado (imutavel)
GET /ledger/skill                   → RPSS/BSS/CRPS com IC e null de permutacao
GET /health/coverage                → cobertura estacao x ano
GET /health/breaks                  → quebras de homogeneidade detectadas
GET /health/sources                 → ultima ingestao, hash, status por fonte
```

`/health/sources` alimenta o painel operacional: uma fonte que falhou vira
lacuna declarada, não exceção silenciosa (ver ARCHITECTURE §1).

---

## 5. Regras de implementação

1. **DuckDB lê o Parquet direto**, sem carregar em memória. Cache por
   `(endpoint, as_of)` — o dado sazonal muda mensalmente, não a cada request.
2. **Sem paginação na v0**: a maior série é ~17k pontos. Adicionar antes de
   precisar é complexidade sem capacidade.
3. **Erro é resposta, não exceção**: fonte ausente → 200 com
   `basis: null` e `limits` preenchido. A central de risco não pode ter tela
   branca.
4. **CORS liberado só para `localhost:5173`** em dev.
5. Toda alteração de contrato bumpa `/api/v1` → `/v2`. O front pinga
   `GET /meta` no boot e avisa se a versão divergir.
