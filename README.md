# Engine Climática RS

Engine de **regimes** climáticos para o Rio Grande do Sul — não um modelo de
previsão isolado. Documento mestre: `manifests/decisions.md` + `feature_blocks.yaml`.

## A restrição que governa tudo

`n_avaliação = 36` (1991–2026). `SE(RPSS) ≈ 0.10–0.15`. O erro padrão é da ordem
do sinal inteiro. Consequência: **não existe arbitragem empírica** entre modelos
próximos — sem forward-greedy, sem contribuição marginal OOF, sem stacker,
sem busca de hiperparâmetro contra a métrica final. A arbitragem é
física + parcimônia + pré-registro.

A escassez só morde na camada supervisionada. As camadas de representação
operam sobre ~17.500 campos diários. **Matemática sofisticada é permitida onde
não toca o alvo; onde toca, ≤6 parâmetros.**

## Demo

**https://yurifreitas.github.io/van-den-climate/**

Demo estática: os dados são uma fotografia congelada em build, e a interface
diz a data no topo. Números vivos exigem a API local — ver *Uso*.

## Estado

| Fase | Entrega | Estado |
|---|---|---|
| 0 | Pré-registro (`feature_blocks.yaml`, ADRs) | ✅ congelado 2026-08-07 |
| 1 | Ingestão + proveniência (CPC, IBGE, JRC) | ✅ 8 fontes |
| 3 | Harness de validação | ✅ verde, roda sem dado |
| 7 | Front React/Vite, 8 visões | ✅ |
| — | Camada municipal (497 municípios) | ✅ ADRs 016–022 |
| — | Camada prospectiva (outlook CPC) | ✅ ADRs 024–028 |
| — | Memória hídrica (JRC 1984–2021) | ✅ ADRs 029–034 |
| 2 | Qualidade + homogeneização | ⬜ |
| 4 | Representação causal (5 operadores) | ⬜ |
| 5 | Regime (HMM/ERA5, M-SSA, análogos) | ⬜ |
| 6 | Modelo ordinal, 5 preditores | ⬜ |
| 8 | Ledger vivo | ⬜ |

O harness veio antes do modelo de propósito (ADR-009): montar a validação
primeiro remove a tentação de afrouxá-la quando o resultado desagradar.

## Uso

```bash
pip install -r requirements.txt
python -m pytest -q                       # gate + harness, roda sem dado

# ingestão (rede; ~130 MB no primeiro run por causa do JRC)
python -m src.ingest.cli                  # índices CPC/PSL
python -m src.ingest.ibge_rs              # MUNIC 2024, malha, população
python -m src.ingest.cpc_enso_advisory    # boletim ENSO
python -m src.ingest.jrc_gsw              # Global Surface Water
python -m src.risk.aguas                  # estatística zonal + overlay

cd web && npm install
.\run.ps1                                 # API :8437 + front :5931
```

Portas próprias, nunca as default: as default colidem com qualquer outro
projeto aberto e o sintoma é enganoso — o front sobe e conversa com a API
errada.

### Atualizar a demo estática

```bash
python -m scripts.build_static_snapshot   # congela a API em web/public/static-api/
git add web/public/static-api && git commit -m "Atualiza snapshot"
```

O CI **não** roda ingestão de propósito: as fontes externas são pesadas e
fora do nosso controle, e uma delas fora do ar derrubaria todo deploy de
código. Atualizar dado é um ato deliberado.

## Invariantes

1. Toda feature declara a defasagem no nome (`oni_lag3_son`, nunca `oni`).
2. O gate anti-vazamento roda **por fold**, e cobre o que ajustou z-score/PCA/CDF
   — não só o valor. Esse é o modo de falha real.
3. Nenhuma métrica é reportada como valor pontual.
4. Aceitação = limite **inferior** do IC 90% de RPSS > 0. Enquanto não passar,
   a climatologia é a previsão vigente — e o front diz isso explicitamente.
5. `FRIO`/`QUENTE` pertencem exclusivamente ao dado. Cromo de interface usa o
   acento próprio (`--acento`), que não pertence a nenhuma escala de dado
   (ADR-023).
6. Mudar `feature_blocks.yaml` por causa de um resultado observado invalida
   o experimento.
7. Todo número derivado carrega `provenance.basis`. No índice municipal o selo
   é **por componente**, não só no envelope (ADR-018).
8. Ausência é `—`, nunca `0`. Município que não respondeu ao IBGE fica fora do
   ranking em vez de ser promovido por falta de dado (ADR-019).

## O que a engine não é

**Não é sistema de alerta de cheia.** Modelos sazonais deslocam probabilidade
de fundo; não preveem eventos individuais. Maio/2024 no RS foi bloqueio
sinótico e transporte de umidade — não sinal ENSO limpo. Nenhuma versão desta
engine o teria previsto, e a interface diz isso na cara do usuário.

A camada municipal é um **índice de prioridade preventiva**, não previsão: ela
ordena onde a próxima tempestade encontra a pior combinação de impacto já
observado, déficit declarado de prevenção e exposição. Responde "se eu tenho
orçamento para 30 municípios antes da primavera, quais 30" — não "onde vai
encher".

**Não há previsão ENSO para 2027.** Horizonte útil de ~9 meses e barreira de
previsibilidade da primavera boreal. Para 2027 o instrumento é o cenário
estrutural, que não depende de saber qual ENSO virá (ADR-026).

**A previsão prospectiva é do CPC/NOAA, não desta engine.** Nenhum modelo
local passou a ADR-007. O boletim entra como contexto (ADR-012) e a interface
mostra os dois lado a lado.

## Fontes

| Fonte | O que traz | Janela |
|---|---|---|
| CPC/PSL | ONI, SOI, AAO, Niño 3.4 | 1950– |
| CPC ENSO Advisory | outlook oficial (contexto) | mensal |
| IBGE MUNIC 2024 | evento climático RS: perigos, danos, plano de contingência | evento 26/04/2024 |
| IBGE malha + SIDRA | 497 polígonos municipais, população | 2024 |
| JRC Global Surface Water | água permanente, sazonal, **perdida**, efêmera | 1984–2021 |

Pekel, J.-F. et al. *High-resolution mapping of global surface water and its
long-term changes.* Nature 540, 418–422 (2016).
