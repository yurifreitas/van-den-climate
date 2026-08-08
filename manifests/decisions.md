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

## Geotécnico, acesso e travessias

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 059 | 2026-08-08 | Perigo geotécnico ganha **camada própria**, e continua fora do índice hídrico | A exclusão da ADR original estava certa (talude e planície têm física, mapa de risco e obra de mitigação diferentes) mas deixava 5 variáveis ingeridas sem uso. Contenção e realocação nunca são dique nem drenagem. Travado por teste | ativa |
| 060 | 2026-08-08 | Ponte é **existência, nunca conservação** | Há 2.159 travessias mapeadas na malha principal e **zero laudo público**: nenhum dado de estado, vão, carga ou ano. Um painel que liste pontes ao lado de um índice de risco convida a leitura "estas pontes estão ruins", que seria invenção. Mesma disciplina de ADR-036 e ADR-053 | ativa |
| 061 | 2026-08-08 | "Manutenção de pontões" vira ação de **vistoria**, nunca de reparo | Sem laudo, o que o dado sustenta é "onde procurar": muitas travessias servindo município que já declarou dano viário e ilhamento. Apontar uma ponte específica seria fabricação | ativa |
| 062 | 2026-08-08 | Recorte de pontes só na **malha principal** (motorway, trunk, primary, secondary) | A malha completa tem dezenas de milhares de travessias, a maioria bueiro vicinal. A pergunta numa cheia é qual travessia isola um município, e essas estão na malha estruturante | ativa |
| 063 | 2026-08-08 | `queda_barreira` conta em **geotécnico E acesso** | Única sobreposição legítima: é talude (geotécnico) e corta estrada (acesso). Não é duplicação — são duas leituras do mesmo fato, com mitigações distintas | ativa |
| 064 | 2026-08-08 | Barragem entra com **dano declarado**, não inventário, e com o efeito a jusante dito | O SNISB/ANA tem o cadastro e a categoria de risco; não está ingerido. E a falha atinge a jusante: o município que sofre pode não ser o que tem a obra | ativa |

**A camada que estava dormindo**: 230 municípios com deslizamento, 250 com
queda de barreira, 179 com corrida de massa, 116 com desabamento de edificação
— todos já ingeridos desde a primeira versão da camada municipal, e nenhum
usado. **397 com dano viário e 205 com áreas ilhadas.**

Os primeiros em perigo geotécnico são Alto Feliz, Arvorezinha, Canela e Bento
Gonçalves — toda a Serra, que é onde deslizamento acontece no RS. Coerência
geográfica que serve de teste de sanidade, não de descoberta.

**obrasgov.gestao.gov.br foi avaliado e descartado**: o filtro `uf=RS` devolve
3 registros e a API responde 429 com facilidade. Não sustenta a camada de
"grandes obras" que o pedido original supunha.

## Mapa de recursos e realocação

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 053 | 2026-08-07 | **É base, nunca viatura.** Nenhum número desta camada representa frota | Não existe dado público de frota de ambulância, viatura policial ou caminhão de bombeiro no RS. "Realocar" aqui só pode significar *onde o vazio é maior diante do risco*; dizer "mova N carros de A para B" exigiria frota, malha viária e modelo de tempo-resposta. Mesma disciplina da ADR-036 | ativa |
| 054 | 2026-08-07 | **Tipo 43 do CNES fica FORA do catálogo** | O rótulo é "Unidade Móvel de Nível Pré-Hospitalar", mas a consulta devolve 3.733 registros no RS encabeçados por PANVEL FARMACIAS. Incluí-lo teria posto quase quatro mil farmácias no mapa como ambulância — erro que passa despercebido porque o total só parece "boa cobertura". Conferido nome a nome. Travado por teste | ativa |
| 055 | 2026-08-07 | O tipo 40 é mantido, mas o **subtipo é heurística sobre o nome**, com `basis: modeled` | O CNES mistura bombeiro voluntário, ambulância, farmácia móvel e unidade odontológica no mesmo tipo. A classificação é útil para leitura e não é cadastro — o estabelecimento segue `measured`, o subtipo não | ativa |
| 056 | 2026-08-07 | Bombeiro e polícia vêm do **OpenStreetMap**, marcados como `completude: colaborativa` | Não há cadastro público aberto do CBMRS nem da Brigada Militar com coordenada. Ausência no mapa **não prova** ausência no território — um vazio ali é hipótese de vazio, e a interface diz isso ao lado do total | ativa |
| 057 | 2026-08-07 | Distância é **linha reta sobre centroide**, declarada como piso | Em cheia a distância real cresce e às vezes deixa de existir quando a rodovia corta. O número é um piso da dificuldade de acesso, nunca estimativa de tempo de rota | ativa |
| 058 | 2026-08-07 | Vazio psicossocial só vira ação onde **já se manifestou** | Distância a CAPS sozinha é geografia. Distância *mais* falha declarada em 2024 é problema. Sem esse duplo critério a lista viraria mapa de densidade populacional | ativa |

**A cobertura do RS**: 1.621 pontos — 346 hospitais, 148 pronto-socorros, 7
centrais de regulação SAMU, 251 CAPS, 163 unidades móveis, 129 quartéis (OSM) e
577 unidades policiais (OSM). Vazios acima de 30 km: **184 municípios sem
quartel próximo, 106 sem CAPS, 101 sem pronto-socorro**. Santa Vitória do
Palmar está a 145 km do pronto-socorro mais próximo.

**Descoberta sobre o SAMU**: das 205 unidades móveis cadastradas, apenas 31 se
identificam por nome como ambulância, resgate ou bombeiro. A frota real opera
sob o CNES da central de regulação, não registrada uma a uma — as 7 centrais
são o sinal confiável de cobertura SAMU; a contagem de móveis **não é**.

## Plano de ação preventiva

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 047 | 2026-08-07 | **Toda ação sai de dado declarado; nenhuma é inferida.** Se o campo falta, a ação não aparece | Uma lista de recomendações sem a linha do dado ao lado é opinião com aparência de sistema. Com a evidência no mesmo cartão, qualquer prefeitura aponta e diz "isso mudou desde 2024", e a correção é uma reingestão, não uma discussão. Travado por teste | ativa |
| 048 | 2026-08-07 | Ausência (`None`) nunca gera ação; só `False` gera | "Não respondeu" não é diagnóstico. Gerar ação a partir de silêncio inverteria a mesma regra que a ADR-019 estabeleceu para o índice | ativa |
| 049 | 2026-08-07 | Dois horizontes: **imediato** (ato administrativo, contrato, treinamento) e **estrutural** (ciclo orçamentário, projeto, obra) | É a única distinção que muda o que o gestor faz na semana que vem. E conecta com a ADR-026: o estrutural é planejável para 2027 justamente por não depender de previsão ENSO | ativa |
| 050 | 2026-08-07 | `esforco` é **escolha editorial declarada**, em três degraus, nunca escala contínua | Não há base de custo de ação preventiva por município. Três degraus separam o que cabe numa primavera do que exige orçamento; uma escala contínua sugeriria precisão inexistente | ativa |
| 051 | 2026-08-07 | Empate no ranking é desfeito por **número de ações imediatas pendentes** | Onde a mesma quantidade de esforço compra mais redução de risco | ativa |
| 052 | 2026-08-07 | A leitura primária é o **agregado estadual**, não o ranking municipal | "206 municípios precisam estruturar apoio psicológico" é uma política; "Restinga Sêca precisa de quatro coisas" é um ofício. Quem decide precisa da primeira antes da segunda | ativa |

**O plano que saiu**: 925 ações em 433 dos 497 municípios, **712 delas
executáveis antes da primavera**. As maiores lacunas do estado, por número de
municípios: apoio psicológico (206), protocolo de evacuação assistida (184),
continuidade dos serviços de saúde (162), alcance do alerta (98), plano de
contingência inexistente (71).

**O que o plano não é**: não é engenharia (sem projeto, custo, prazo ou
dimensionamento), não é priorização por custo-benefício, e não substitui o
Plano Municipal de Redução de Riscos nem o plano de contingência da Defesa
Civil — aponta a ausência deles.

## História longa — e o CONTATO COM O ALVO

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 041 | 2026-08-07 | **GHCN-Daily** como base histórica de chuva: 66 estações dentro do polígono do RS, 1934–1999, 942.831 dias-estação | É a série mais longa que existe publicamente para o RS. Preenche o vazio entre a teleconexão (ONI desde 1950) e o impacto de um evento (MUNIC 2024): a resposta observada do território à chuva, ano a ano | ativa |
| 042 | 2026-08-07 | **ESTE É O CONTATO COM O ALVO (ADR-004).** A partir daqui, `feature_blocks.yaml` está congelado *de fato* | O cálculo do trio da ADR-002 sobre chuva observada olha a variável que a engine tenta prever. Mudar a regra de redução depois disso invalida o experimento (Invariante 6). Declarado no payload em `meta.contato_com_alvo`, não só aqui | ativa |
| 043 | 2026-08-07 | A camada é **descritiva**: contagem e intervalo por reamostragem. Nenhum modelo ajustado, nenhum preditor selecionado | Selecionar preditor aqui seria escolher em função do alvo — exatamente o que a ADR-004 existe para impedir. Qualquer modelo continua tendo de passar a ADR-007 | ativa |
| 044 | 2026-08-07 | Recorte das estações **por polígono municipal**, nunca por caixa | A caixa do RS pega Santa Catarina: Taió, Ituporanga, Joaçaba e São Joaquim entrariam como se fossem RS | ativa |
| 045 | 2026-08-07 | Temporada OND só conta com ≥80 dos 92 dias | Com menos, a frequência de dias úmidos vira função de quantos dias faltam, não de chuva | ativa |
| 046 | 2026-08-07 | IC por **bootstrap**, não teste-t, com semente fixa | n por fase é de uma a duas dezenas e a distribuição de p95 não é normal. Semente fixa para que o número na tela não mude entre recargas | ativa |

### O resultado

Primeira vez que a engine mede a própria afirmação central com dado próprio.
**50 primaveras (1950–1999), 66 estações**, deslocamento El Niño − Neutro:

| Alvo (ADR-002) | Δ | IC 90% | |
|---|---|---|---|
| Frequência de dias úmidos | +0,032 | [+0,005, +0,059] | separa de zero |
| Intensidade em dia úmido | +2,18 mm/dia | [+0,51, +3,88] | separa de zero |
| p95 diário | +5,33 mm | [+1,33, +9,64] | separa de zero |
| Total da estação | +97,8 mm | [+25,1, +175,5] | separa de zero |

Ordenação El Niño > Neutro > La Niña coerente nas quatro métricas — o que é
teste de sanidade do *join*, não descoberta climatológica.

**O que isto NÃO significa**: que a engine tem previsão validada. Um composto
diz que anos de El Niño foram mais úmidos *em média*; a ADR-007 exige RPSS com
limite inferior de IC 90% acima de zero *em previsão fora da amostra*. São
afirmações diferentes, e nenhum modelo passou a segunda. A heurística de
`api/routers/risk.py` continua `modeled`, não `measured` — o que mudou é que
agora ela tem lastro no dado do próprio projeto, não só em literatura.

**Limite mais caro da camada municipal, e que a interface repete em três lugares**: o
MUNIC é auto-declaração municipal sobre **um** evento. Há incentivo assimétrico
— relatar dano dá acesso a repasse, relatar falha de prevenção não dá nada. Um
município poupado em 2024 por sorte de trajetória aparece com impacto baixo.
O índice ordena prioridade; ele não mede risco absoluto.
