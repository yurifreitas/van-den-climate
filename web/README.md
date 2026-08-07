# Central de Risco Climatico RS — Front (web/)

Front em Vite + React + TypeScript para a Central de Risco Climatico RS
(ADR-013/014, `manifests/decisions.md`). Consome o contrato congelado em
`docs/API_CONTRACT.md`, NAO a API rodando — a API pode estar em construcao
em paralelo, e o front usa MSW para simular o contrato em dev/teste.

## Rodar

```bash
cd web
npm install
npm run dev      # http://localhost:5173, proxy /api -> localhost:8000, MSW ativo por padrao
npm run build    # tsc -b + vite build -> dist/
npm run test     # vitest run (inclui o teste de grep da paleta)
npm run preview  # serve o build de producao localmente
```

Para desligar o mock e falar com uma API real em `localhost:8000` durante o
dev, rode com `VITE_USE_MSW=false npm run dev`.

## Mapa rota -> pergunta que ela responde

| Rota | Pergunta |
|---|---|
| `/` (Risco) | Quais perigos climaticos estao ativos agora no RS, por horizonte? O perigo sinotico (`flash_flood`) sempre aparece, mesmo fora de escopo. |
| `/estado` | Em que percentil da distribuicao historica esta cada modo climatico (ENSO/SAM/...), e ha quanto tempo essa fase persiste (Regua de Surpresa)? |
| `/previsao` | O que a previsao sazonal desloca em relacao a climatologia, e passou no criterio de aceitacao? (`not_accepted` e um resultado, nao um erro.) |
| `/evidencia` | O que sustenta a previsao — atribuicao por bloco, contrafactual sem ENSO, anos analogos? |
| `/ledger` | O que foi previsto de fato vs observado, e qual o skill medido com intervalo de confianca? |
| `/saude` | A rede de estacoes tem cobertura suficiente, ha quebras de homogeneidade, e as fontes de ingestao estao vivas? |

## Decisoes de biblioteca

- **Charting: Recharts.** SVG declarativo em componentes React (sem
  imperativo tipo Plotly/D3 cru), API estavel, curva de manutencao baixa
  para as familias de grafico do brief (serie divergente, tercis, barras de
  atribuicao). Trocaria por D3 cru so se precisassemos de interacao
  totalmente customizada — nao e o caso aqui.
- **Sem MUI/Chakra.** CSS proprio em `theme/tokens.css` + CSS por
  componente, porque a direcao visual (tipografia Archivo Expanded/Inter
  Tight/IBM Plex Mono, paleta de 6 cores) e incompativel com o vocabulario
  visual de um design system generico.

## Regra da paleta (critica, nao negociavel)

`FRIO` (#3E7FA8) e `QUENTE` (#C1553A) sao EXCLUSIVAS DO DADO — nenhum
elemento de UI usa essas cores. Elas vivem isoladas em
`src/theme/chartColors.ts`; todo o resto do app usa apenas
abissal/carta/giz/bruma (`src/theme/tokens.css`). A regra e verificada por
`src/theme/__tests__/palette.test.ts`, que faz grep em `src/` e falha se os
hex aparecerem fora de `src/theme/`.

## Estrutura

```
src/
  api/            cliente fetch + tipos TS do contrato + hooks TanStack Query + mocks MSW
  components/     apresentacao pura (ProvenanceBadge, HazardCard, graficos, layout)
  theme/          tokens.css (UI) + chartColors.ts (FRIO/QUENTE, isolado)
  views/          as 6 rotas
```

## Selo de proveniencia

Todo painel com numero derivado renderiza `<ProvenanceBadge basis={...} />`
(`src/components/ProvenanceBadge.tsx`): borda solida = medido, tracejada =
modelado/sintetico, pontilhada = fonte ausente. Sempre em giz/bruma.
