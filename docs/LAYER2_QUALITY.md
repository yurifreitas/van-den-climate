# Camada 2 — Qualidade e homogeneização

O caminho crítico do projeto. Não é o ENSO: os índices são arquivos-texto de KB,
estáveis há décadas, e já estão ingeridos. É a **precipitação** — porque ela é o
alvo, e porque uma série mal homogeneizada não degrada a métrica, ela a *melhora*.

---

## 1. Por que este é o único erro que a validação não pega

O harness (Camada 6) protege contra vazamento temporal e contra seleção sobre
ruído. Não protege contra isto:

> Uma estação troca de sensor em 2003. A média sobe 4%. O modelo aprende que
> "anos recentes são mais chuvosos", o que correlaciona com a tendência de
> aquecimento, e o bloco `trend` ganha peso. O RPSS **sobe**. O walk-forward
> aprova. E a engine aprendeu a assinatura de um instrumento, não do clima.

Nenhum teste estatístico distingue isso de sinal, porque estatisticamente *é*
sinal — só não é sinal climático. A única defesa é metadado e detecção explícita
de quebra, antes da modelagem. Daí a Camada 2 ser bloqueante.

---

## 2. As quebras conhecidas do RS

| Quebra | Quando | Efeito típico |
|---|---|---|
| **Convencional → automática (INMET)** | 2000–2008, por estação | Descontinuidade em intensidade e em contagem de dias úmidos. A automática registra traços que a convencional arredondava para zero — inflando `wetday_freq`, que é um dos três alvos |
| Mudança de horário de observação | variável | Desloca a atribuição de chuva entre dias consecutivos. Afeta `p95` mais que o acumulado |
| Relocação de estação | variável, mal documentada | Salto de nível sem mudança de variância |
| Troca de pluviômetro (ANA) | variável | Muda a resolução de registro (0,1 vs 0,5 mm) |
| Digitalização de arquivo histórico | anos 1990 | Erros de vírgula decimal — outliers de 10× |

A primeira é a mais perigosa **precisamente porque coincide com o período de
avaliação** (1991–2026) e com a tendência real. Confundi-las é o modo de falha
central do projeto.

---

## 3. Ordem de operações

```
1. METADADO      ← primeiro, sempre. Histórico de estação do INMET/ANA.
                   Quebra documentada não precisa ser detectada.
2. VALIDAÇÃO     ← limites físicos, ausente≠zero, sequências impossíveis
3. DETECÇÃO      ← quebras não documentadas, contra série de referência regional
4. MÁSCARA       ← estação-ano utilizável ou não. NÃO corrigir — mascarar.
5. HOMOGENEIZAR  ← só onde houver referência confiável, e declarando o ajuste
```

**A decisão que economiza meses**: prefira **mascarar** a corrigir. Um ajuste de
homogeneização mal-feito é indetectável a jusante; uma lacuna declarada apenas
reduz n — que já é o parâmetro que estamos gerenciando conscientemente. Com
n=36, perder 3 estações-ano é barato. Aprender a assinatura de um sensor não é.

---

## 4. Validação física — as regras

| Regra | Ação |
|---|---|
| `prcp < 0` | INVALID |
| `prcp > 300 mm/dia` | SUSPECT — verificar contra vizinhas (recorde RS ~ 250–300) |
| Ausente | `NaN` + flag. **Nunca zero.** Confundir "não mediu" com "não choveu" enviesa `wetday_freq` para baixo, e é o erro mais comum em dado de estação brasileira |
| Sequência de ≥10 zeros exatos em estação úmida | SUSPECT — assinatura de sensor travado |
| Valor idêntico repetido ≥3 dias com `prcp>0` | SUSPECT |
| Acumulado mensal com <20 dias válidos | mês inutilizável para os alvos |

O limiar de dia úmido é **1,0 mm** (não 0,1), e essa escolha não é arbitrária:
é o limiar padrão em climatologia justamente porque torna a série robusta à
troca convencional→automática, que difere sobretudo em traços.

---

## 5. Detecção de quebra — método

Testes clássicos (SNHT, Pettitt, Buishand) aplicados **à razão contra uma série
de referência regional**, nunca à série bruta. Aplicar à série bruta confunde
quebra com tendência climática real — que é exatamente o que queremos separar.

A referência é a média ponderada de 3–5 estações vizinhas correlacionadas
(r > 0,7 no período comum), elas próprias ainda não homogeneizadas. Isso é
circular, e a saída é iterar: detectar, mascarar, recalcular a referência.
Duas iterações bastam na prática.

**Cuidado com o n**: esses testes têm potência baixa em série curta. Uma quebra
não detectada não é prova de ausência de quebra. Por isso o metadado vem antes:
quebra documentada é certeza; quebra detectada é hipótese.

---

## 6. Máscara de confiabilidade — a saída da camada

Grade estação × ano, com um valor por célula:

| Nível | Significado | Uso |
|---|---|---|
| `usable` | ≥90% de dias válidos, sem quebra no ano | tudo |
| `degraded` | 70–90% de dias válidos | só agregados robustos (`wetday_freq`), não `p95` |
| `broken` | quebra documentada ou detectada neste ano | excluído |
| `absent` | <70% | excluído |

Essa máscara é **exposta na interface** (`/health/coverage`), não escondida. Um
usuário da central de risco precisa poder ver que a estação dele tem buraco de
1987 a 1994 — porque isso muda o quanto ele deve confiar no número.

---

## 7. A estratégia de duas fontes

Nenhuma fonte isolada serve:

- **CHIRPS** (0,05°, 1981–) é homogênea por construção e cobre o estado inteiro,
  mas é um produto misto satélite+estação: subestima extremos e já "viu" as
  estações, o que contamina qualquer validação contra elas.
- **INMET/ANA** dá o dado real de estação com série longa, mas é heterogêneo.

Uso proposto: **INMET/ANA define o alvo** (é o que o usuário reconhece e o que a
bacia sente); **CHIRPS serve como série de referência regional** para a detecção
de quebra e para preencher o mapa entre estações. A contaminação importa menos
nesse papel, porque a referência só precisa ser *homogênea*, não *acurada*.

MERGE-CPTEC é melhor que CHIRPS em qualidade, mas começa em 2000 — curto demais
para servir de referência ao período de âncora. Entra como verificação cruzada
no período comum, não como base.

---

## 8. Critério de saída da fase

A Camada 2 está pronta quando:

1. Toda estação candidata tem histórico de metadado registrado ou explicitamente
   marcado como indisponível.
2. A máscara estação×ano existe e é servida por `/health/coverage`.
3. As quebras convencional→automática estão datadas por estação em
   `/health/breaks`.
4. Existe um conjunto de estações com `usable` cobrindo 1951–2026 suficiente
   para definir os três alvos — e se **não** existir, esse é o achado mais
   importante do projeto e muda o escopo, não é um problema a contornar.

O item 4 é o risco real: é possível que nenhuma estação do RS tenha série
utilizável contínua desde 1951. Nesse caso a âncora da ADR-001 precisa ser
renegociada contra o dado, e é melhor descobrir isso agora do que na Fase 6.
