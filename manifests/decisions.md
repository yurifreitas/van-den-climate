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

## Camada municipal — prioridade preventiva

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 016 | 2026-08-07 | Camada municipal entra como **índice de prioridade preventiva**, nunca como previsão de cheia | É a única formulação falsificável com o dado que existe. Previsão municipal de enchente exigiria modelo hidrodinâmico por bacia, cota de rio em tempo real e chuva prevista em malha fina — nada disso está nesta engine, e a ADR-013 permanece intacta | ativa |
| 017 | 2026-08-07 | Fonte primária = IBGE MUNIC 2024, suplemento "Evento Climático Rio Grande do Sul" (497 municípios × 100 variáveis) | É a única base pública que responde, por município: quais perigos hídricos ocorreram em 26/04/2024, qual foi o dano, e — decisivo — se havia plano de contingência, se foi executado e **por que não** (recurso financeiro, humano, material, sistema de alerta, treinamento). Responde a pergunta de manutenção preventiva que nenhuma base climática responde | ativa |
| 018 | 2026-08-07 | Cada componente do índice carrega `basis` **próprio**; o composto é `modeled` | O índice mistura medido (impacto e déficit, declarados ao IBGE), modelado (perigo sazonal) e ausência declarada (manutenção de ativos). Um `basis` único no topo apagaria justamente a distinção que o §0 existe para preservar | ativa |
| 019 | 2026-08-07 | **Cobertura mínima de peso (0.60) + exigência de impacto ou déficit presente** para publicar índice | Escrito depois de o modelo pôr Bagé em 1º com 90/100 por *não ter respondido* ao MUNIC: sobrou exposição (peso 0.28), a renormalização esticou o componente único para a escala toda e a lacuna virou manchete. Numa lista de prioridade, promover a ausência é pior que subestimar. Travado por `tests/test_risk_municipal.py` | ativa |
| 020 | 2026-08-07 | Cortes de nível **fixos** no índice, nunca quantis | Quantil garantiria "N% críticos" independentemente da realidade — o índice viraria ranking disfarçado de diagnóstico, e um ano em que tudo melhora apareceria idêntico a um ano em que tudo piora | ativa |
| 021 | 2026-08-07 | Componente `manutencao_ativos` existe no contrato **sempre nulo**, com motivo | Casas de bomba, diques e comportas — o modo de falha central em Porto Alegre em 2024 — não têm base pública municipal no RS. Campo ausente parece campo que ninguém precisou; campo nulo com motivo é dívida declarada | ativa |
| 022 | 2026-08-07 | Perigo sazonal (H) entra como multiplicador **estadual e uniforme**, com piso 0.62 | O ONI não tem resolução municipal e não pode fingir que tem: H desloca o nível de todos e nunca reordena. O piso impede que o índice zere fora da estação, o que ensinaria o gestor a desligar a atenção — o oposto do objetivo preventivo |ativa |
| 023 | 2026-08-07 | Acento de **interface** (menta/violeta) fora da paleta de dado | A regra 5 do projeto reserva FRIO/QUENTE ao dado, o que na prática deixara a UI inteira em cinza. Um acento que não pertence a nenhuma escala de dado resolve o contraste sem violar a regra: nenhuma leitura confunde cromo com anomalia | ativa |

## Camada prospectiva — o que dá para dizer sobre 2026 e sobre 2027

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 024 | 2026-08-07 | Boletim ENSO do CPC/NOAA ingerido como **contexto**, exibido com autoria externa explícita | Cumpre a ADR-012 sem mutilá-la: o boletim não entra em `feature_blocks.yaml`, não alimenta a Camada 3 e não toca o alvo. Omiti-lo fazia a central parecer cega quando a informação existe, é pública e é oficial. O painel diz "CPC/NOAA" no cabeçalho e "esta engine: sem previsão aceita" ao lado — a comparação é o conteúdo | ativa |
| 025 | 2026-08-07 | Índice municipal ganha **três cenários de horizonte**: `atual`, `ond2026`, `estrutural` | São três perguntas diferentes, não três graus de pessimismo. O que muda entre elas é a natureza da evidência | ativa |
| 026 | 2026-08-07 | **Não existe previsão ENSO para 2027 nesta central.** Para 2027+ o instrumento é o cenário `estrutural` | Horizonte útil de previsão ENSO é de ~6–9 meses e a barreira de previsibilidade da primavera boreal degrada o que atravessa o primeiro semestre. OND/2027 a partir de ago/2026 está a 14 meses — fora de qualquer skill publicada. A resposta correta não é um ONI inventado: impacto observado, déficit de prevenção e exposição **não expiram**, e por isso são planejáveis com anos de antecedência. Um município sem plano de contingência em 2024 continua sem plano em 2027 até alguém escrever um | ativa |
| 027 | 2026-08-07 | No cenário `estrutural`, `perigo_sazonal` é `null`, nunca `0.0` | `0.0` diria "prevemos ENSO neutro em 2027", que é uma afirmação — e uma que ninguém sustenta a 14 meses. Travado por teste | ativa |
| 028 | 2026-08-07 | Saturação do multiplicador é **declarada no payload** (`leitura_saturacao`) | Sob o outlook de OND/2026 o multiplicador bate no teto (1.00) e os cenários `ond2026` e `estrutural` produzem números idênticos. Não é bug: significa que a previsão não aplica desconto nenhum. Dois painéis com números iguais e nenhuma explicação parecem erro de software | ativa |

**Consequência prática, e a razão de a camada existir**: o CPC dá 81% de chance
de El Niño **muito forte** em OND/2026 — a temporada-alvo desta engine. Isso
torna a lista de prioridade preventiva acionável *nesta* primavera, e o cenário
estrutural a torna acionável para 2027 sem depender de previsão nenhuma.

## Memória hídrica — onde já foi água

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 029 | 2026-08-07 | **JRC Global Surface Water v1.4** (1984–2021) como fonte de hidrografia e de mudança de água | Único produto público que classifica cada pixel de 30 m como água permanente, sazonal, **perdida** ou nova ao longo de quatro décadas. `perdida` + `efêmera` é a melhor resposta que dado público permite para "áreas que voltaram a encher": terreno com precedente de água, hoje seco no mapa oficial | ativa |
| 030 | 2026-08-07 | Recorte **pela malha municipal**, nunca por retângulo | A primeira versão contou o Atlântico: 106.000 km² de "água permanente" num estado de 281.000. Erro de máscara é silencioso — não levanta exceção e produz um mapa que continua bonito. Travado por `tests/test_aguas.py` | ativa |
| 031 | 2026-08-07 | Memória hídrica **fica FORA do índice composto** | O RS tem ~1,1 milhão de ha de arroz irrigado por inundação. Lavoura alagada é água sazonal para sensor óptico de 30 m — indistinguível de banhado. Incluir a variável reordenaria a prioridade preventiva em favor de municípios arrozeiros sem que a causa ficasse visível. Entra como dimensão paralela até existir máscara de agricultura irrigada. Travado por teste, para que a inclusão exija ADR nova em vez de mudar 497 números publicados em silêncio | ativa |
| 032 | 2026-08-07 | Ordem de pintura: água de hoje **por cima** de água de antes | A margem de todo rio tem histórico de água. Pintar `perdida` por cima acusaria de passivo hídrico a margem de cada rio do estado | ativa |
| 033 | 2026-08-07 | O cruzamento JRC × MUNIC 2024 é apresentado como **evidência não circular** | A série do JRC termina em 2021 e não conhece a cheia de maio de 2024. Uma base é óptica e anterior ao evento; a outra é declaratória e posterior. Se o JRC incluísse 2024 a concordância não valeria nada | ativa |
| 034 | 2026-08-07 | **Não existe camada de 150 anos.** A janela é 1984–2021 e o payload diz isso | Não há base pública vetorial da hidrografia do RS do século XIX — o que existe são cartas históricas em acervo, imagem e não geometria. Fingir cobertura de 150 anos seria a fabricação mais fácil e mais cara desta camada | ativa |

**Confirmação geográfica que a camada produziu**: os primeiros colocados em
fração de água perdida são Nova Santa Rita e Charqueadas — planície do baixo
Jacuí, imediatamente a montante de Porto Alegre — e a lista do cruzamento traz
Esteio e Campo Bom, no vale do Sinos. Todos entre os mais atingidos em maio de
2024, identificados por uma série que termina em 2021.

## Resposta, vulnerabilidade e recuperação — o depois do evento

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 035 | 2026-08-07 | As 54 colunas restantes do MUNIC entram como **domínio próprio**, fora do índice de prioridade | Descrevem consequência e resposta, não predisposição. Somá-las transformaria a lista de "onde agir antes" num ranking de quem sofreu mais — outra pergunta, que já tem resposta própria | ativa |
| 036 | 2026-08-07 | Capacidade de saúde é **estabelecimento, nunca leito** | O CNES-LT do DATASUS é `.dbc` sem API. A razão entre estabelecimento e leito varia de 10 a 400 entre um hospital de interior e um terciário; chamar um de outro vira decisão de encaminhamento errada, e passa despercebido porque o número continua plausível. Travado por teste | ativa |
| 037 | 2026-08-07 | "Não houve/não necessitou" nas escalas logísticas é **não-aplicável**, nunca nota máxima | Município que não precisou de resgate não demonstrou capacidade de resgate. Tratar como 1.0 premiaria quem foi poupado e enterraria quem foi testado — inverteria o sinal que a escala mede. Travado por teste | ativa |
| 038 | 2026-08-07 | Índice de autonomia é média **só das escalas aplicáveis** | Município testado em duas capacidades e bem nas duas não pode ser penalizado por não ter sido testado nas outras cinco | ativa |
| 039 | 2026-08-07 | A tradução das 7 escalas ordinais fica **escrita como tabela literal** em `ESCALAS` | Converter texto ordinal em número é interpretação, não ingestão. Deixá-la explícita permite que quem discorde aponte a linha exata — inclusive nas duas escalas de fornecimento, cuja direção declarei por leitura e não por definição do IBGE | ativa |
| 040 | 2026-08-07 | Mapa de risco municipal do ano corrente vai para a **tela inicial** | "Onde está o risco agora" é a razão de existir da central e não pode exigir navegação. O detalhamento continua em `/municipios` | ativa |

**Achados que a camada produziu**: 201 dos 497 municípios não têm hospital nem
pronto-socorro (mediana de 13,5 km até a unidade mais próxima; pior caso
Maçambará, 55,9 km). 242 tiveram o sistema de saúde afetado em 2024. **206
municípios não ofereceram apoio psicológico às vítimas**, contra 228 que
ofereceram.

**Cinco lacunas declaradas no payload** (`/resposta/municipios.lacunas`), não
em nota de rodapé: contagem de leitos, dias letivos perdidos, recuperação
financeira, alcance do apoio psicológico e prazo/custo de reconstrução. Cada
uma nomeia a fonte que a resolveria.

**Limite mais caro da camada municipal, e que a interface repete em três lugares**: o
MUNIC é auto-declaração municipal sobre **um** evento. Há incentivo assimétrico
— relatar dano dá acesso a repasse, relatar falha de prevenção não dá nada. Um
município poupado em 2024 por sorte de trajetória aparece com impacto baixo.
O índice ordena prioridade; ele não mede risco absoluto.
