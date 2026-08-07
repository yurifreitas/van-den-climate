# Front — Engine Climatica RS

Instrumento de auditoria, nao dashboard de previsao (§9.1). Existe para
tornar visivel a distancia entre o que foi **medido** e o que e **prior**.

## Como rodar

```bash
pip install streamlit plotly pandas numpy pyarrow
streamlit run app/main.py
```

Sem nenhum dado real em `data/interim` ou `data/features`, o app sobe usando
`app/fixtures.py` — series sinteticas deterministicas (seed fixa) que
respeitam o esquema de `src/contracts.py`. Toda visao que usa fixtures exibe
o selo `DADO SINTETICO`. Assim que os parquets reais aparecerem nos caminhos
listados em `app/data_source.py::EXPECTED`, o front troca de fonte sozinho no
proximo reload, sem flag manual — o selo vira `DADO MEDIDO`.

## Mapa das visoes

| Visao | Pergunta que responde |
|---|---|
| **Estado** | O presente e raro ou comum, variavel por variavel? (Regua de Surpresa: percentil causal + trilha de 12 meses, mesma escala para todos os canais) |
| **Previsao** | O que a engine emite para OND — e como isso se compara a climatologia, com intervalo? (nunca um numero sozinho) |
| **Evidencia** | De onde vem o numero — quanto e ENSO, quanto e SAM/Atlantico Sul/tendencia, e o que sobra removendo ENSO? |
| **Ledger** | A engine ja acertou antes? Historico append-only, previsto vs observado, sem reavaliacao retrospectiva |
| **Saude dos dados** | O dado aguenta a pergunta? Cobertura estacao x ano, lacunas, e a quebra convencional->automatica do INMET; diagrama de confiabilidade |

## Arquivos

- `theme.py` — paleta e regra dura: `FRIO`/`QUENTE` sao exclusivos do dado.
- `fixtures.py` — geradores sinteticos deterministicos (ONI, SAM, TSM Atlantico
  Sul, chuva diaria por estacao, ledger de previsoes, estado de surpresa).
- `data_source.py` — deteccao automatica dado real vs sintetico, um
  `resolve_*` por serie, sempre retornando `(df, is_synthetic, source_path)`.
- `charts.py` — todas as figuras Plotly (Regua de Surpresa, series com banda
  divergente, tercis, atribuicao por bloco, ledger, cobertura, confiabilidade).
- `main.py` — as 5 visoes, plugando `data_source` + `charts`, com estados
  vazios como convite a acao quando a camada correspondente ainda nao existe.

## Testes

```bash
python -m pytest tests/test_app.py -q
```

Cobrem: fixtures validas contra `contracts.validate_series`; toda funcao de
`charts.py` produz uma `go.Figure` serializavel sem lancar; a regra de
paleta (nenhum elemento de interface usa os hex de `FRIO`/`QUENTE`).
