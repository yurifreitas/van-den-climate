# Arquitetura — extração escalável e camadas

Complementa o documento mestre. Onde o mestre lista *quais* fontes, este diz
*como* elas entram sem que a engine apodreça em seis meses.

---

## 1. Por que a extração é o problema difícil

O ledger de graus de liberdade (n=36) diz que a modelagem tem pouco espaço.
A consequência menos óbvia: **o esforço migra para a extração**. 70% do trabalho
real está nas Fases 1–2, e é lá que os erros são invisíveis — um modelo ruim
aparece na métrica, uma série mal homogeneizada *melhora* a métrica.

Três propriedades que a camada de extração precisa ter, em ordem de importância:

1. **Reprodutibilidade** — poder responder, daqui a um ano, "de onde veio este
   número". Sem hash e timestamp de download, não há resposta.
2. **Idempotência** — reprocessar não deve mudar nada. Fontes como o INMET
   *revisam retroativamente*; sem detecção, a série muda em silêncio.
3. **Degradação parcial** — a queda do HidroWeb não pode derrubar o pipeline
   inteiro. Fonte que falha vira lacuna declarada, não exceção não capturada.

Velocidade não está na lista. Volume total do projeto (excluindo ERA5) cabe em
poucos GB.

---

## 2. Medalhão de quatro estágios

```
   REDE
     │  fetch  ── retry+backoff+jitter, timeout, cache por sha256
     ▼
  raw/        imutável · payload byte-a-byte + provenance.json
     │  parse ── formato → esquema único de contracts.py
     ▼
  interim/    parquet por fonte · esquema validado · quality_flag
     │  quality ── homogeneização, detecção de quebra, máscara
     ▼
  curated/    parquet · série utilizável, com máscara de confiabilidade
     │  represent ── os 5 operadores (causais, expanding)
     ▼
  features/   parquet particionado por ano-alvo · com FeatureProvenance
```

A fronteira que mais importa é **raw → interim**. `raw/` é sagrado: nunca
editado, nunca regenerado. Se o parser estava errado, corrige-se o parser e
reprocessa-se de `raw/` — sem tocar a rede. Isso torna o desenvolvimento do
parser barato, que é a diferença entre tratar as idiossincrasias do INMET com
cuidado ou desistir e interpolar.

### Por que não um banco

DuckDB sobre Parquet cobre tudo que este projeto precisa: consulta analítica
sobre arquivos, sem servidor, sem migração, versionável. Um Postgres aqui
adicionaria operação sem adicionar capacidade.

---

## 3. Detecção de revisão retroativa

O modo de falha silencioso mais perigoso: a fonte muda o passado.

Cada ingestão compara o parse novo com o `interim/` vigente **restrito ao
período comum**. Diferenças em valores já publicados geram um registro em
`data/revisions/<source_id>.jsonl` e um alerta — não uma sobrescrita silenciosa.

Isso importa cientificamente, não só operacionalmente: se o ONI de 1997 mudou
entre a calibração e a avaliação, o walk-forward está medindo outra coisa.
ERSST e o próprio ONI **de fato** revisam (mudança de período-base, novas
versões do produto). O `product_version` no manifesto de proveniência existe
exatamente para isso.

---

## 4. Escalabilidade por classe de fonte

As fontes não são homogêneas e não devem ser tratadas com o mesmo mecanismo.

| Classe | Exemplos | Volume | Estratégia |
|---|---|---|---|
| **Índices** | ONI, SOI, AAO, PDO, EMI | KB | Download completo a cada vez. Diff barato. Sem incremental — a complexidade não se paga. |
| **Grades pequenas** | ERSST, HadISST, GPCC | ~centenas de MB | NetCDF completo por versão; recorte para a caixa de interesse na etapa de parse. |
| **Grades grandes** | ERA5, ERA5-Land, CHIRPS | dezenas de GB | **Nunca** baixar o campo global. Recorte espacial e de variável na própria requisição (`cdsapi` aceita `area`). Particionar por ano. Só os campos de `sources.yaml:era5.fields`. |
| **Estações** | INMET, ANA | ~centenas de MB | Uma requisição por estação-ano, paralelizada com limite de concorrência baixo (4–6) e backoff agressivo. Cache por estação-ano: uma estação-ano já baixada nunca é rebaixada. |

O caso das estações é onde a paralelização importa: ~300 estações × 65 anos são
milhares de requisições contra uma API instável. A regra é **concorrência baixa
e cache granular**, não concorrência alta — a API do INMET degrada sob carga e
passa a devolver respostas truncadas que *parecem válidas*.

### A armadilha do ERA5

O CDS enfileira requisições; uma requisição mal dimensionada fica horas na fila.
Divida por ano e por variável, guarde o `request_id`, e trate a fila como
assíncrona de verdade. Uma requisição de 1940–2026 global é um erro de
principiante que custa uma semana.

---

## 5. Fronteira de execução paralela

O que pode rodar em paralelo, sem coordenação:

- **Ingestores** entre si — dependem só da rede e escrevem em prefixos disjuntos.
- **Operadores de representação** por variável — são funções puras sobre séries.
- **Folds do walk-forward** — cada ano-alvo é independente por construção.

O que **não** pode:

- Homogeneização entre estações vizinhas (a detecção de quebra usa referência
  regional; é um problema de grafo, não embaraçosamente paralelo).
- Ajuste da PCA por bloco (precisa de todos os sinais do bloco no mesmo fold).

Consequência prática para o desenvolvimento com agentes: as fronteiras de
diretório (`src/ingest/`, `src/represent/`, `app/`) coincidem com fronteiras
reais de acoplamento. Não é conveniência de processo — é a estrutura do problema.

---

## 6. Contratos entre camadas

Cada fronteira tem um contrato verificável, e cada contrato tem um teste.

| Fronteira | Contrato | Onde é imposto |
|---|---|---|
| rede → raw | provenance.json com os 5 campos obrigatórios | `ingest/base.py` |
| raw → interim | esquema único, sem NaN com flag OK | `contracts.validate_series` |
| interim → curated | máscara de confiabilidade por estação-ano | Camada 2 |
| curated → features | nome declara defasagem; `FeatureProvenance` populada | `validate/leakage.gate` |
| features → modelo | exatamente 5 preditores, ≤6 parâmetros | `feature_blocks.yaml` + ADR-003 |
| modelo → ledger | previsão imutável com timestamp de emissão | append-only |

O contrato mais sutil é o penúltimo: `FeatureProvenance` exige `fitted_on`, os
timestamps usados para **ajustar** z-score, PCA, CDF do PIT e o AR. O vazamento
real neste projeto quase nunca é usar o valor futuro — é ajustar a normalização
no conjunto completo. Um pipeline pode respeitar perfeitamente o corte de
30/set e ainda assim vazar por essa via.

---

## 7. Ordem de destravamento

```
cpc_oni + psl_nino + cpc_soi  ──→  bloco enso_state
cpc_oni (série longa)         ──→  bloco enso_dynamics (M-SSA, inovação)
cpc_aao + bas_marshall        ──→  bloco sam           (PSA exige ERA5)
ersst_v5                      ──→  blocos satl + trend
chirps_v2 + inmet             ──→  o ALVO (trio OND)
era5                          ──→  Camada 4 (HMM de regime, EOFs de PSA)
```

Os quatro primeiros são arquivos-texto de KB, estáveis há décadas — dão os 5
blocos preditores em uma tarde. O gargalo real é o alvo: CHIRPS é a melhor grade
longa (1981–), mas o INMET é o que dá densidade de estação, e é o que exige a
Camada 2 inteira. **A precipitação, não o ENSO, é o caminho crítico do projeto.**

---

## 8. O que fica de fora, deliberadamente

- **Orquestrador** (Airflow/Prefect/Dagster) — a cadência é sazonal, não diária.
  Um `make` e um cron resolvem. Reavaliar só quando houver ingestão operacional
  contínua na Fase 8.
- **Streaming / tempo real** — o alvo é trimestral. Latência não é requisito.
- **Feature store** — o Parquet particionado é a feature store.
- **Ingestão de previsões dinâmicas como feature** (NMME, SEAS5, plumas IRI) —
  ADR-012: contexto, não preditor, na v1.

Cada uma dessas é uma coisa que parece profissional e que, aqui, só adiciona
superfície de falha entre você e a única pergunta que importa: o limite inferior
do IC de RPSS é maior que zero?

---

## 9. A segunda metade: da ingestão à tela

As seções 1–8 descrevem como o dado **entra**. Depois do pivô para central de
risco (ADR-013) existe uma segunda metade, e ela tem regras próprias.

```
  data/interim/*.parquet
        │
        │  src/risk/*.py   ── uma camada por pergunta, sem estado
        │                     lê parquet, devolve dataclass com
        │                     rows + resumo + limites
        ▼
  api/routers/*.py          ── envelopa com provenance, pagina, e
        │                     traduz FileNotFoundError em 503 com
        │                     a instrução de qual ingestor rodar
        ▼
  web/src/api/*.ts          ── cliente escrito à mão contra o contrato
        │
        ▼
  web/public/static-api/    ── snapshot: a API congelada em arquivos,
                              para a demo pública sem backend
```

### A regra das camadas de risco

Toda camada devolve **três coisas**: as linhas, um resumo, e os **limites** —
uma lista de frases que dizem onde aquele número deixa de valer. `limites` não é
opcional e não é rodapé: `tests/test_hidrologia.py::test_declara_os_proprios_limites`
falha se a lista encolher.

Nenhuma camada guarda estado. As caras (`dossie.py`) usam `lru_cache` por
`(cenário, oni)` porque a alternativa é remontar a tabela do estado inteiro para
descartar 496 linhas — 4,2 s por dossiê, mais de meia hora nos 497 do snapshot.
**O objeto em cache é compartilhado e somente lido**; quem precisar mutar copia
antes, ou o dossiê de um município contamina o do próximo.

### O snapshot estático, e por que ele é o árbitro

O CI **não** roda ingestão: as fontes são pesadas e fora do nosso controle, e uma
delas fora do ar derrubaria todo deploy de código. Em vez disso,
`scripts/build_static_snapshot.py` congela cada rota num arquivo JSON, e o front
em modo estático lê esses arquivos.

Isso tem um efeito colateral que virou a defesa mais útil do projeto: **o
snapshot é o único artefato do repositório gerado pela API**. `types.ts` é
escrito à mão contra o contrato, e os fixtures do MSW são escritos à mão contra
a expectativa do front — dois artefatos à mão erram **juntos, na mesma direção**,
e nada acusa. Foi assim que `vazios` virou envelope no back, continuou array no
tipo, e a demo subiu em branco com `s.map is not a function`, com CI verde.

Por isso `web/src/views/__tests__/telas-contra-snapshot.test.tsx` renderiza as
doze telas contra o snapshot real, e não contra fixture.

### A função gêmea

`slugEstatico` existe em duas linguagens — `web/src/api/client.ts` e
`scripts/build_static_snapshot.py` — e precisa concordar caractere a caractere.
Se divergirem, o front pede um arquivo que o build não gerou, e a demo quebra
**só em produção**. `tests/test_static_snapshot.py` compara as duas.

---

## 10. Como uma camada nova entra

A ordem abaixo não é burocracia: cada passo existe porque a ausência dele já
produziu um defeito neste repositório.

1. **Entrada em `manifests/sources.yaml`**, com `hazards`. Travado por
   `tests/test_docs.py::test_todo_ingestor_tem_fonte_no_catalogo` — onze
   ingestores viveram fora do catálogo.
2. **Ingestor** que grava bruto + proveniência e falha alto. O modo de falha a
   evitar não é a exceção: é o parquet íntegro afirmando um estado falso (o WFS
   que devolve 200 com geometria nula, e o estado sai com zero km²).
3. **Camada de risco** com `rows + resumo + limites`, e a tradução (o julgamento)
   fora da ingestão — a ingestão grava o que a fonte afirma (ADR-080).
4. **Rota**, com envelope de proveniência e selo aninhado quando a proporção
   medido/traduzido mudar lá dentro (ADR-093).
5. **Tipo, hook e tela**; verificação com `npm run build`, não com
   `tsc --noEmit` — o build roda `tsc -b`, que checa o projeto inteiro.
6. **Snapshot regerado e commitado.**
7. **ADR** para cada escolha que alguém questionaria em seis meses.
8. **Documentação**: `docs/DADOS.md` e `docs/MODELOS.md`, travados por teste.

