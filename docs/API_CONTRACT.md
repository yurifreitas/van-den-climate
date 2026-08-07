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

## 3b. Risco municipal (497 municípios do RS)

```
GET /risk/municipal?level=&limit=    → índice de prioridade preventiva, os 497
GET /risk/municipal/{cod_mun}        → decomposição de um município + posição
GET /geo/municipios                  → malha municipal (GeoJSON, IBGE)
```

**Não é previsão de cheia** (ADR-016). É um índice de *prioridade preventiva*:
ordena onde a próxima tempestade encontra a pior combinação de impacto já
observado, déficit declarado de prevenção e exposição humana. A ADR-013
permanece intacta — nenhuma camada desta engine antecipa evento individual.

```json
{
  "as_of": "2026-08-07",
  "provenance": {"basis": "modeled", "horizon": "seasonal",
                 "source_ids": ["ibge_munic_rs", "ibge_pop_rs", "cpc_oni"]},
  "model_card": {"formula": "R = 100 * (0.38*I + 0.34*D + 0.28*E) * (0.62 + 0.38*H)",
                 "pesos": {...}, "cortes": {...}, "limites": [...]},
  "n_total": 497, "n_completo": 459, "n_parcial": 37, "n_insuficiente": 1,
  "municipios": [
    {"cod_mun": 4315503, "municipio": "Restinga Seca",
     "score": 60.8, "level": "high", "basis": "modeled", "completude": "completo",
     "componentes": {
       "impacto":           {"valor": 0.75, "basis": "measured", "detalhe": {...}},
       "deficit_prevencao": {"valor": 0.46, "basis": "measured", "detalhe": {...}},
       "exposicao":         {"valor": 0.76, "basis": "measured", "detalhe": {...}},
       "perigo_sazonal":    {"valor": 0.82, "basis": "modeled",
                             "detalhe": {"escopo": "estadual — uniforme para os 497"}},
       "manutencao_ativos": {"valor": null, "basis": null,
                             "detalhe": {"motivo": "sem fonte publica municipal..."}}
     }}
  ]
}
```

Quatro regras específicas desta seção:

1. **`basis` por componente, não só no envelope** (ADR-018). O índice mistura
   medido, modelado e ausência declarada; um selo único apagaria a distinção
   que o §0 existe para preservar.
2. **`score: null` + `completude: "insuficiente"`** quando a cobertura de dado
   não alcança o mínimo do modelo (ADR-019). Nunca `0` — zero afirma "avaliado
   e sem risco", que é outra afirmação. O município continua no payload: não
   responder ao IBGE não pode escondê-lo nem promovê-lo.
3. **`manutencao_ativos` sempre presente e sempre nulo** (ADR-021), com motivo.
   É dívida declarada, não campo esquecido.
4. **`model_card` no payload**, não só na documentação: índice composto sem os
   pesos publicados não é auditável — quem lê não consegue refazer a conta nem
   discordar com precisão.

### Horizonte — `?cenario=`

```
?cenario=atual        → H do ONI medido (temporada publicada)
?cenario=ond2026      → H do outlook oficial do CPC para a temporada-alvo
?cenario=estrutural   → SEM H: o único instrumento defensável para 2027+
```

```
GET /outlook/enso                    → boletim ENSO do CPC (contexto, ADR-012)
```

**Não há previsão ENSO para 2027 nesta API** (ADR-026). Horizonte útil ~6–9
meses e a barreira de previsibilidade da primavera boreal. No cenário
`estrutural` o componente `perigo_sazonal` vem `valor: null, basis: null` com
motivo — nunca `0.0`, que afirmaria "prevemos ENSO neutro em 2027".

`/outlook/enso` carrega `autoria` (CPC/NOAA) e `engine_local.tem_previsao_aceita:
false` **no mesmo payload**: confundir "o CPC prevê" com "esta engine prevê"
é a falha mais cara possível numa central que existe para separar o que sabe
do que supõe. Ausente → 200 com `disponivel: false`, não 503: a lacuna não
quebra nada a jusante e o risco estrutural não depende de previsão.

### Memória hídrica — onde já foi água

```
GET /geo/aguas/meta                  → bbox, cores, totais por categoria, limites
GET /geo/aguas.png                   → overlay RGBA alinhado ao bbox
GET /risk/municipal/cruzamento/aguas → memória hídrica × inundação declarada 2024
```

Fonte: **JRC Global Surface Water v1.4**, série Landsat **1984–2021**. Quatro
categorias por município, em `MunicipalRow.aguas`:

| categoria | leitura |
|---|---|
| `permanente` | rio e lago de hoje |
| `sazonal` | várzea, banhado — **e lavoura de arroz irrigada** |
| `perdida` | **era água e deixou de ser**: leito abandonado, banhado drenado |
| `efemera` | encheu uma vez dentro da série e sumiu |

`memoria_hidrica = perdida + efemera` — terreno com precedente de água que hoje
não é água no mapa oficial.

**Fora do índice composto** (ADR-031): água sazonal de satélite não separa
banhado de arroz irrigado, e o RS tem ~1,1 milhão de ha de arroz por inundação.
`model_card.memoria_hidrica.no_indice` é `false` e o motivo vem junto.

**A série termina em 2021 e não contém a cheia de maio de 2024** — e é isso que
torna `/cruzamento/aguas` honesto: as duas bases não se conhecem, então
concordância entre elas é evidência, não circularidade.

**Não cobre 150 anos** (ADR-034). Não existe base pública vetorial da
hidrografia do RS do século XIX.

Base municipal ausente → **503 com instrução de ingestão**, nunca síntese. Inventar
impacto de enchente por município seria a pior fabricação possível nesta
central; é o único ponto do contrato onde a regra §5.3 (fonte ausente vira
resposta declarada) cede para um erro explícito.

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
