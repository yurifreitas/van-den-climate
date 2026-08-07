# Log de Decisões (ADR) — Engine Climática RS

Append-only. Uma decisão revogada não é apagada: recebe `SUPERSEDED by ###` e
uma linha nova é adicionada. Alterar retroativamente destrói a auditoria.

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 001 | 2026-08 | Âncora fixa 1951–1990; avaliação 1991–2026 (n=36) | Única configuração onde a calibração causal não vaza e o percentil tem resolução | ativa |
| 002 | 2026-08 | Alvo = trio (freq. dias úmidos, intensidade, p95), não o acumulado OND | Mais amostra por alvo, mais informação física, captura o que a média esconde | ativa |
| 003 | 2026-08 | Camada supervisionada ≤6 parâmetros | n=36 → ~6 obs/parâmetro é o limite defensável | ativa |
| 004 | 2026-08 | Regra de redução pré-registrada e datada antes do contato com o alvo | Sem isso, seleção sobre ruído fabrica RPSS inteiro | ativa — `feature_blocks.yaml` congelado em **2026-08-07** |
| 005 | 2026-08 | Ancoramento por variável: teleconexão em base relativa; alvo de impacto em base ancorada | Atmosfera responde a gradiente relativo (razão do RONI); a bacia responde a mm absolutos | ativa |
| 006 | 2026-08 | M-SSA no lugar de MPI | Mesma família modal, mas com literatura climática e benchmarks — ganha falsificabilidade externa | ativa |
| 007 | 2026-08 | Aceitação: limite inferior do IC 90% de RPSS > 0 (bootstrap em blocos) | "RPSS positivo" pontual não significa nada com n=36 | ativa |
| 008 | 2026-08 | Sem TCN, assinaturas, TDA, rough paths, RLS na v1 | Infalsificáveis neste tamanho de amostra | ativa |

## Decisões de processo (§8.2 / §12)

| # | Data | Decisão | Razão |
|---|------|---------|-------|
| 009 | 2026-08-07 | Harness de validação (Camada 6) construído **antes** das Camadas 3–5 | Remove a tentação de afrouxar o critério quando o resultado desagradar |
| 010 | 2026-08-07 | Gate anti-vazamento como teste de CI bloqueante | Vazamento temporal é o único erro que não aparece na métrica |
| 011 | 2026-08-07 | Front React só a partir da Fase 7; Streamlit até lá | Front sobre pipeline instável é a forma mais cara de descobrir erro na Camada 2 |
| 012 | 2026-08-07 | Plumas IRI/CPC e NMME/SEAS5 são **contexto**, não feature, na v1 | Previsão de modelo dinâmico como preditor introduz vazamento de informação futura e dependência operacional não reproduzível no hindcast |

## §12 — resolução das três decisões abertas

1. **Âncora 1951–1990**: confirmada (ADR-001). n=36 aceito em troca de saber
   exatamente o que está sendo medido.
2. **Trio de alvos**: confirmado (ADR-002). O acumulado OND permanece como
   alvo secundário reportado, nunca como métrica de aceitação.
3. **`feature_blocks.yaml`**: escrito e congelado em 2026-08-07, com
   `target_contact: false`. Nenhum código de modelagem antes disso — cumprido.

## Pivô de front — Central de Risco

| # | Data | Decisão | Razão |
|---|------|---------|-------|
| 013 | 2026-08-07 | **Revoga ADR-011.** Front em Vite + React + TypeScript desde já, servido por API FastAPI sobre DuckDB/Parquet | Decisão do dono do projeto: o alvo não é um instrumento de leitura sazonal, é uma **central de risco**. Isso implica multi-perigo, múltiplos usuários, séries operacionais e alerta — requisitos que o Streamlit não sustenta e que mudam o desenho de dados, não só o de tela |
| 014 | 2026-08-07 | A fronteira estável passa a ser o **contrato de API**, não o layout de Parquet | Mitiga o risco que a ADR-011 protegia: o front pode ser construído em paralelo à Camada 2 porque a API absorve mudanças de esquema. Se o contrato vazar detalhe de armazenamento, o risco volta |
| 015 | 2026-08-07 | Streamlit rebaixado a ferramenta interna de depuração, não descartado | Continua sendo o caminho mais rápido para inspecionar uma série nova durante o desenvolvimento da Camada 2 |

**Consequência não óbvia da central de risco**: a engine sazonal desloca
probabilidade de fundo e **não prevê eventos individuais** (§5, Risco 3). Uma
central de risco que só tenha a camada sazonal comunicará mais confiança do que
possui. O desenho precisa separar, na própria interface e na API, os horizontes:

| Horizonte | O que a engine pode dizer | Camada |
|---|---|---|
| Sazonal (OND) | desloca probabilidade de tercil | atual, Fases 4–6 |
| Sub-sazonal (2–6 sem) | janelas favoráveis via MJO/regime | Fase 9, não construída |
| Sinótico (1–7 d) | **nada** — exige modelo dinâmico | fora de escopo, sempre |

Maio/2024 no RS foi bloqueio sinótico. Nenhuma versão desta engine o teria
previsto, e a central de risco precisa dizer isso na cara do usuário.
