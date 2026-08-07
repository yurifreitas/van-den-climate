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

## Estado

| Fase | Entrega | Estado |
|---|---|---|
| 0 | Pré-registro (`feature_blocks.yaml`, ADRs) | ✅ congelado 2026-08-07 |
| 3 | Harness de validação | ✅ 9 testes verdes, sem dado |
| 7 | Front Streamlit, 5 visões + Régua de Surpresa | ✅ esqueleto |
| 1 | Ingestão + proveniência | ⬜ próximo |
| 2 | Qualidade + homogeneização | ⬜ |
| 4 | Representação causal (5 operadores) | ⬜ |
| 5 | Regime (HMM/ERA5, M-SSA, análogos) | ⬜ |
| 6 | Modelo ordinal, 5 preditores | ⬜ |
| 8 | Ledger vivo | ⬜ |

O harness veio antes do modelo de propósito (ADR-009): montar a validação
primeiro remove a tentação de afrouxá-la quando o resultado desagradar.

## Uso

```bash
pip install pandas numpy pyarrow duckdb streamlit pytest pyyaml
python -m pytest tests -q          # gate + harness, roda sem dado
streamlit run app/main.py
```

## Invariantes

1. Toda feature declara a defasagem no nome (`oni_lag3_son`, nunca `oni`).
2. O gate anti-vazamento roda **por fold**, e cobre o que ajustou z-score/PCA/CDF
   — não só o valor. Esse é o modo de falha real.
3. Nenhuma métrica é reportada como valor pontual.
4. Aceitação = limite **inferior** do IC 90% de RPSS > 0. Enquanto não passar,
   a climatologia é a previsão vigente — e o front diz isso explicitamente.
5. `FRIO`/`QUENTE` pertencem exclusivamente ao dado. Cor no front sempre
   significa anomalia.
6. Mudar `feature_blocks.yaml` por causa de um resultado observado invalida
   o experimento.

## O que a engine não é

Não é sistema de alerta de cheia. Modelos sazonais deslocam probabilidade de
fundo; não preveem eventos individuais. Maio/2024 no RS foi bloqueio sinótico
e transporte de umidade — não sinal ENSO limpo.
