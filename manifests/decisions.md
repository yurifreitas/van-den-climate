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
