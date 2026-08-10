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

## Geometria do sistema — atrator, recorrência, fractal

Camada de **representação**, autorizada pelo README ("matemática sofisticada é
permitida onde não toca o alvo") e submetida ao mesmo critério da ADR-008: não
"isso é sofisticado?", mas **"eu consigo falsificar isso com o n que tenho?"**.

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 065 | 2026-08-08 | Todo método declara o **n que exigiria** e o n disponível; quem não passa é recusado por escrito | Recusa sem número é preconceito. `RECUSADOS` nomeia o que faltou em cada caso | ativa |
| 066 | 2026-08-08 | Surrogate **IAAFT**, não de fase simples, e n ≥ 200 | O de fase impõe amplitude gaussiana e faz o teste rejeitar a hipótese errada. E com 20 surrogates o menor p possível é 0,048 — reportar isso era reportar o piso de resolução, não a evidência | ativa |
| 067 | 2026-08-08 | **Dimensão de correlação do ENSO é inestimável**, definitivamente | D = 3,08 exige 100.284 pontos mensais por Smith = 8.357 anos. O registro instrumental (ERSSTv5, 1854) dá ~2.060. Déficit de 49×. Não é limitação da ingestão — é do registro, e não muda em horizonte humano | ativa |
| 068 | 2026-08-08 | Resultado de não linearidade sempre reportado sobre série **não suavizada** | A média móvel de 3 meses do ONI quase dobra o z: 3,21 → 5,78 na mesma série. O achado sobrevive na bruta (z=3,21, p=0,010), mas a magnitude do ONI é artefato do filtro | ativa |
| 069 | 2026-08-08 | Espectro multifractal reportado **só pelo lado de q positivo** | Com 61% de dias secos, o lado negativo mede o descarte de segmentos, não a dinâmica. Dava largura 3,0 onde a resposta é 0,14 | ativa |
| 070 | 2026-08-08 | DFA com escala máxima em **n/10**, nunca n/4 | Com n/4 sobram 4 segmentos na maior escala e a média instável enviesa a reta inteira: em ruído branco devolvia H = 0,44 onde a resposta é 0,5. Travado por teste sobre 6 sementes | ativa |
| 071 | 2026-08-08 | Teste de geometria **detecta o próprio recorte inválido** antes de refutar | Mascarar água pela malha municipal remove 84% dela (Patos e Mirim ficam fora), justamente o corpo compacto procurado. Sem a checagem, o teste "refutaria" a classificação de regime por artefato | ativa |

### Os três regimes de amostra do projeto

| n | camada | o que sobrevive |
|---|---|---|
| 36 | temporadas de avaliação | nada sofisticado — é a razão da ADR-003 e da ADR-008 |
| 918 | ONI / Niño 3.4 mensal | recorrência sim; dimensão só com ressalva; Lyapunov não |
| 942.831 | chuva diária, 67 estações | multifractal, DFA e Wasserstein são confortáveis |

### O que se sustenta

- **Não linearidade no ENSO**: DET = 0,815 na série bruta contra p95 de 0,793
  em 200 surrogates IAAFT, z = 3,21, p = 0,010. Estrutura além de espectro
  **e** distribuição.
- **Horizonte de previsibilidade = 8,98 meses**, medido na recorrência. A
  ADR-026 afirmava "~9 meses" como citação de literatura; agora é medida
  independente, sem modelo e sem ajuste.
- **Persistência na chuva**: H mediana 0,560 (IQR 0,545–0,569), **66 de 66
  estações com H > 0,5**. Sem uma exceção.
- **Multifractalidade fraca**: largura mediana 0,139 (IQR 0,119–0,156).

### O que NÃO se sustenta, e foi retratado

- **El Niño vs Neutro em Wasserstein**: W = 97,8 contra p95 nulo de 98,3 —
  **não separa** (p = 0,053). Só El Niño vs La Niña sobrevive (p < 0,0001). O
  contraste que a engine sustenta é El Niño contra La Niña, não contra Neutro.
- **Barreira da primavera**: previ o mínimo em março–junho; caiu em fevereiro.
  A checagem pré-declarada retornou falso, e não foi movida para acomodar.
- **Classificação de regime**: segue **NÃO TESTADA**. O teste geométrico é
  inválido por recorte, não refutação.

**Fronteira**: nada aqui seleciona preditor nem entra em `feature_blocks.yaml`,
congelado desde a ADR-042. É descrição de geometria; uso preditivo teria de
passar pela ADR-007.

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

## ADR-072 a 076 — Territórios tradicionais e o dossiê municipal

A central tinha dez camadas e nenhum lugar onde elas se encontrassem. Um
gestor municipal não tem dez perguntas; tem uma — *o que eu preciso saber
sobre a minha cidade para decidir?* — e respondê-la exigia visitar dez telas
e fazer a junção de cabeça.

O dossiê faz a junção. A decisão de projeto que o organiza é a **ordem**:
onde estou → qual o perigo → quem está exposto → com o que conto → o que
falhou → o que fazer → **o que não sei**. A numeração aparece na tela de
propósito; um painel de decisão sem ordem declarada vira lista de widgets e
cada leitor inventa a própria sequência.

| # | Data | Decisão | Razão | Estado |
|---|------|---------|-------|--------|
| 072 | 2026-08-08 | O dossiê **não carrega selo de proveniência próprio**; cada bloco carrega o seu | Um selo único sobre dez camadas apagaria a diferença entre medido, modelado e ausente — que é a informação mais importante quando a decisão é cara. Travado por `test_nao_ha_selo_unico_no_topo` | ativa |
| 073 | 2026-08-08 | O bloco de lacunas é o **bloco 7**, com o mesmo peso visual dos outros — nunca rodapé | Quem decide sem saber o que a central não sabe decide pior do que quem não a consultou. As lacunas são propagadas do payload de cada camada, não escritas à mão, para que uma lacuna nova apareça sozinha | ativa |
| 074 | 2026-08-08 | Território tradicional **nunca é convertido em número de pessoas** | O polígono não traz população. Converter área exposta em gente exposta exige o setor censitário do Censo 2022, não ingerido. `test_nunca_afirma_populacao` proíbe qualquer campo que convide à leitura | ativa |
| 075 | 2026-08-08 | Ausência de território mapeado **não é ausência de comunidade**, e o resumo é obrigado a dizer isso | O viés é sistemático e numa direção só: quem tem menos acesso a Estado tem menos chance de ter processo fundiário aberto. Um vazio no mapa provavelmente significa ausência de política fundiária, não ausência de gente | ativa |
| 076 | 2026-08-08 | `situacao_juridica` sempre visível ao lado do nome do território | Terra em estudo e terra homologada são o mesmo polígono e realidades opostas em conflito fundiário. Omitir o campo faz o painel afirmar direito que não foi concedido | ativa |
| 077 | 2026-08-08 | O gatilho de drenagem urbana é **percentil 90 do próprio estado** (com piso de 1%), não limiar absoluto | O 8% herdado vinha da literatura de cobertura impermeável, que mede **bacia**; a fração aqui é de **município** e inclui toda a área rural — erro de categoria de uma ordem de grandeza, que deixava passar 13 municípios de 497. "Entre os 10% mais impermeabilizados do RS" é verificável; "passou de 8%" não era. O limiar apurado (1,90%) viaja no payload | ativa |
| 078 | 2026-08-08 | Toda pessoa do catálogo de referências carrega `work` — a peça por onde entrar | Nome e afiliação sem obra informam reputação, não leitura: o leitor sabia que devia ler Runge e não sabia o quê. Valia para 83 das 86 entradas. Travado por `test_toda_pessoa_tem_obra` | ativa |
| 079 | 2026-08-08 | Onde a contribuição é dispersa, `work` **declara a dispersão** ("Corpo de trabalho…") em vez de forjar citação | O remédio da 078 tem efeito colateral óbvio: inventar um título redondo para preencher campo. Isso afirmaria fonte verificável inexistente — o mesmo modo de falha que a ADR-002 persegue nos números, e mais grave que o vazio porque não se vê | ativa |
| 080 | 2026-08-08 | A tradução **ordem do SiBCS → grupo hidrológico** mora no risco, nunca na ingestão | A ingestão grava o que o IBGE afirma; o grupo é julgamento nosso, apoiado em literatura e passível de estar errado sem que o mapa esteja. Se morasse no parquet, medido e modelado sairiam do mesmo arquivo com a mesma cara e ninguém a jusante saberia qual é qual | ativa |
| 081 | 2026-08-08 | As três camadas do BDiA são **cruzadas célula a célula**, não usadas como três tabelas ao lado | O Curve Number pergunta o par (solo, cobertura). Com tabelas separadas só restaria supor independência — e ela é falsa numa direção conhecida: a lavoura procura o solo profundo, a mata sobra na encosta. A média resultante não descreveria pedaço nenhum do município | ativa |
| 082 | 2026-08-08 | O escoamento é publicado **sempre em par**, solo seco e solo encharcado (AMC II e III) | O desastre acontece na terceira chuva, não na primeira. Um CN2 de 74 vira 87 sob umidade antecedente alta e o escoamento quase dobra sem uma gota a mais. Publicar só a condição média descreveria um estado que quase nunca é o do evento | ativa |
| 083 | 2026-08-08 | A classe de erosão é **posição no estado**, nunca corte absoluto da literatura | A RUSLE não tem teto em declividade e P=1 remove a única defesa que existe no campo: em encosta ela devolve centenas de t/ha/ano, valor que o perfil raso torna impossível de sustentar. Importar "50 = alta" carimbaria metade do estado. Travado por `test_classe_e_posicao_no_estado` | ativa |
| 084 | 2026-08-08 | Ao lado do índice de erosão vão os **números medidos** que sobrevivem à contestação dele | 70.042 km² sob uso intensivo em declive e 37.048 km² de solo raso sob lavoura são área cruzando duas classes do IBGE — não passam por tabela nenhuma. Se o índice cair, a camada continua de pé, e é ele que deve ser contestado | ativa |
| 085 | 2026-08-08 | Recursos passam a ter **família**, e papéis de famílias diferentes **nunca se somam** | Hospital e supermercado respondem perguntas diferentes: um atende ferido, o outro decide se a cidade come na quinta. Um "total de recursos" misturando os dois não significaria nada. Travado por `test_todo_papel_pertence_a_uma_familia` | ativa |
| 086 | 2026-08-08 | Abrigo é **potencial**, nunca cadastro — e nenhum campo emite capacidade | Escola e ginásio no OSM são prédio grande e coberto: não declaram vagas, banheiro, cozinha, acessibilidade nem gerador, e a lista real é decisão da Defesa Civil municipal, que não publica. Somar "vagas de abrigo" a partir disso seria inventar o número que mais importa. Travado por `test_abrigo_nunca_emite_capacidade` | ativa |
| 087 | 2026-08-08 | Todo recurso carrega **exposição hídrica** — cruzamento com a memória hídrica do JRC | Um mapa de recursos responde "onde estão"; não respondia a pergunta que 2024 fez: quais saem de operação junto com o evento. Hospital que alaga não é capacidade, vira demanda no pior momento. O cruzamento é com satélite 1984-2021, sem conhecimento do evento — se um recurso aparece exposto e alagou, são duas fontes independentes concordando | ativa |
| 088 | 2026-08-08 | A exposição é da **célula de ~500 m**, e o payload é obrigado a dizer isso | Não há cota, profundidade nem defesa: prédio atrás de dique aparece exposto do mesmo jeito, porque o satélite viu água ali antes do dique. É fila de inspeção, nunca laudo de vulnerabilidade | ativa |
| 089 | 2026-08-08 | Cor no mapa de recursos é por **família**, não por papel | O categórico do projeto tem seis cores validadas sob deuteranopia e a regra é explícita: nunca cicla. Com dezessete papéis, colorir por papel exigiria reciclar tom — escola e subestação dividiriam a mesma cor e a identidade, única coisa que a cor categórica garante, iria embora | ativa |
| 090 | 2026-08-09 | Entra chuva **atual** (NOAA CPC diário, até ontem) — a primeira fonte não histórica de precipitação | A central tinha chuva histórica que termina em 2022 e oceano do mês corrente, e não sabia quanto choveu na semana passada. Sem isso, publicava dois Curve Numbers e deixava a escolha para quem lesse — o que na prática significa que ninguém escolhia | ativa |
| 091 | 2026-08-09 | A condição de umidade antecedente é **medida**, e o payload publica o CN vigente | A tabela SCS determina a condição pela chuva dos 5 dias anteriores, e essa chuva agora existe. Hoje: 139 municípios em AMC III, 155 em AMC I — e o deslocamento de CN chega a ±20 pontos | ativa |
| 092 | 2026-08-09 | A estação de crescimento no RS (outubro a abril) é **definição nossa** e viaja no payload | A tabela original não data a estação, porque quem a usava sabia. No hemisfério sul a escolha é nossa e desloca o limiar em quase 26 mm: 30 mm em 5 dias é solo encharcado em julho e apenas condição média em janeiro | ativa |
| 093 | 2026-08-09 | O bloco `hoje` carrega selo **`measured`** dentro de um envelope `modeled` | Ali a proporção entre medido e traduzido é outra: a chuva de 5 dias é observação, e só a conversão para classe e CN é tabela. Esconder isso sob o selo do envelope perderia a única coisa nova que a camada traz | ativa |
| 094 | 2026-08-09 | Entra **declividade medida** (Copernicus DEM 90 m) no lugar do adjetivo da carta | O fator LS cresce quarenta vezes do plano ao montanhoso; num fator com essa alavanca, a diferença entre "ondulado" e "forte ondulado" dominava o resultado, e estava sendo decidida por um adjetivo que descreve o polígono inteiro pela feição predominante | ativa |
| 095 | 2026-08-09 | O LS da carta é **reancorado** pelo DEM, não substituído por ele | Cada um sabe algo que o outro não sabe: a carta diz QUAL parte do município é mais íngreme — informação que a média do DEM apaga — e o DEM diz QUANTO. A forma vem da carta, a magnitude vem da medida; trocar um pelo outro perderia metade da informação nas duas direções | ativa |
| 096 | 2026-08-09 | O fator de reancoragem é **publicado**, não aplicado em silêncio | Mediana estadual 1,06 — a carta acerta na média do estado — mas o fator varia de 0,14 a 2,60 entre municípios: ela erra onde a decisão acontece. Sem publicar o fator, a troca de método apareceria como um número novo sem explicação | ativa |
| 097 | 2026-08-10 | O mapa desenha no máximo **6.000 pontos**, com o descarte declarado na tela | A tela de recursos travava o navegador: cada ponto rendia dois nós de DOM (`<circle>` + `<title>`), e com as cinco famílias ligadas os 18,7 mil pontos viravam ~37 mil nós — que o `hover`, sendo estado do próprio mapa, re-renderizava a cada movimento do mouse. Acima do teto o mapa do estado já é mancha contínua: não há densidade a mais para ler, só custo a pagar. Travado por `MapaMunicipal.test.tsx` | ativa |

### O que a camada de territórios encontrou

**40 territórios** com centroide dentro do RS: 29 quilombolas e 11 terras
indígenas (Guarani, Guarani Mbyá, Kaingang).

O achado que não era esperado: **35% deles estão em bacia lagunar**, contra 8%
dos municípios do estado — concentração de 4×. Bacia lagunar é o regime em que
o nível é governado por vento, não por chuva local, e em que a drenagem por
gravidade falha justamente quando mais se precisa dela. A concentração é
histórica, não climática: terra remanescente é a terra que sobrou, e a que
sobra é a de várzea.

Casca aparece com **15,7% do território com memória hídrica** — área que foi
água entre 1984 e 2021 e hoje não é. Campo dos Poli está a **79,9 km da
unidade de urgência mais próxima**, em linha reta ao centroide; a estrada real
é sempre mais longa.

### Custo de montagem, e por que ele importa

O dossiê não calcula nada — ele junta. Mas a junção ingênua remontava a tabela
do estado inteiro, o plano dos 497 municípios, o geotécnico, o raster dos
territórios e o mapa de recursos **por município consultado**, para descartar
496 linhas: 4,2 s por dossiê. Nos 497 do snapshot estático isso seria mais de
meia hora, e na API 4 s de espera por clique. Com as camadas montadas uma vez
por `(cenário, oni)`, o segundo dossiê em diante custa ~0 ms. O objeto em
cache é compartilhado e somente lido — quem precisar mutar copia antes, ou o
dossiê de um município contamina o do próximo.
