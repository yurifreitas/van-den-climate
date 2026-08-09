# Modelos — o que cada número afirma, e como derrubá-lo

Todo módulo em `src/risk/` transforma dado em afirmação. Este documento lista,
para cada um: **a pergunta**, **a conta**, **os parâmetros que viajam no
payload**, e **como falsificá-lo**.

A última coluna é a que importa. Um modelo que não diz como seria refutado não é
modelo, é opinião com decimais.

---

## 0. A fronteira que atravessa todos

`measured` é observação. `modeled` é qualquer coisa que passou por tradução,
tabela, ajuste ou julgamento. `synthetic` é dado gerado para desenvolvimento.

A tentação recorrente — e a que os testes mais perseguem — é lavar procedência
por origem: *"veio de um mapa do IBGE, logo é medido"*. Não é. A fração de solo
é medida; o **grupo hidrológico** dela é tradução nossa. O cadastro de recursos
é medido; a **ordem** da lista de vazios é composta. Por isso vários payloads
carregam selos aninhados, e o selo de dentro pode ser mais forte que o de fora
(ADR-093).

---

## 1. Índice de prioridade preventiva — `municipal.py`

**Pergunta:** entre 497 municípios, onde a prevenção rende mais antes da
temporada?

**Conta:** média ponderada de componentes com pesos declarados — impacto
observado (MUNIC), déficit de prevenção (MUNIC), exposição (população), memória
hídrica (JRC), manutenção de ativos (**sempre nulo**, ADR-021) — multiplicada
por um perigo sazonal estadual e uniforme.

**Parâmetros no payload:** peso de cada componente, cobertura mínima (0,60),
cortes de nível **fixos** e o multiplicador de perigo com piso 0,62.

**Como derrubar:** mostre um município no topo cuja cobertura de peso vem de um
componente só. Foi assim que Bagé apareceu em 1º com 90/100 por *não ter
respondido* ao MUNIC — a renormalização esticou o componente único para a escala
toda e a lacuna virou manchete (ADR-019).

**Onde ele não vale:** não é previsão de cheia, nunca foi. Previsão municipal
exigiria modelo hidrodinâmico por bacia, cota de rio em tempo real e chuva
prevista em malha fina — nenhum dos três existe aqui (ADR-016).

---

## 2. Contenção — `contencao.py`

**Pergunta:** que famílias de intervenção o dado deste município justifica?

**Conta:** nenhuma. É um catálogo de estratégias com **gatilhos físicos**: cada
estratégia só aparece onde o gatilho existe no dado — regime de bacia (ANA),
ocorrência geotécnica declarada (MUNIC), memória hídrica (JRC) ou superfície
construída (GHSL).

**Parâmetro que mudou de natureza:** o gatilho de drenagem urbana era `0,08`
absoluto, herdado da literatura de cobertura impermeável. Aquela literatura mede
**bacia**; a fração aqui é de **município**, que inclui toda a área rural —
denominadores diferentes por uma ordem de grandeza. O corte passou a ser o
**percentil 90 do próprio estado** com piso de 1% (hoje 1,90%), calculado a cada
build e declarado no payload: *"está entre os 10% mais impermeabilizados do RS"*
é verificável; *"passou de 8%"* não era (ADR-077).

**Como derrubar:** mostre uma estratégia disparando onde o mecanismo físico não
existe, ou um mecanismo real sem estratégia correspondente.

**Onde ele não vale:** nenhuma entrada é projeto. São famílias de intervenção;
dimensionamento, custo e prazo exigem estudo fora desta central.

---

## 3. Balanço de chuva — `hidrologia.py`

**Pergunta:** dos 100 mm que caem, quantos infiltram?

**Conta:** Curve Number (SCS/NRCS).

```
S  = 25400/CN − 254           capacidade de retenção (mm)
Ia = 0,2 · S                  perda inicial
Q  = (P − Ia)² / (P − Ia + S) se P > Ia, senão 0
```

O CN composto vem do **cruzamento** solo × cobertura × relevo do BDiA, ponderado
por área, com a superfície construída medida (GHSL) entrando por cima — e não
dentro do rótulo urbano do IBGE, para não contar o asfalto duas vezes.

A chuva de projeto vem de Gumbel sobre máximos anuais do GHCN, na estação mais
próxima do centroide. A velocidade de resposta é **ordinal** — sem talvegue nem
declividade medida não existe tempo de concentração em minutos.

**Parâmetros no payload:** `razao_ia` (0,2), tempos de retorno publicados,
distância à estação de chuva e quantos anos ela tem.

**Como derrubar:** três caminhos abertos, e todos estão em
`manifests/references.yaml` como leitura adversarial.
1. **Hawkins**: a base que originou o método não sustenta Ia = 0,2S; 0,05S
   ajusta melhor na maioria das bacias. Por isso a razão é parâmetro, não
   constante embutida.
2. **Beven**: sem calibração contra vazão, a incerteza plausível do CN composto
   pode ser maior que a diferença entre municípios que o payload ordena.
3. Prova de sanidade contra o mapa: Muitos Capões (Latossolo profundo do
   planalto) dá CN 52; Nova Bréscia (Neossolo Litólico do Vale do Taquari, a
   encosta que a cheia de 2023 levou) dá 86. Se essa separação sumir, o modelo
   deixou de descrever o estado.

**Onde ele não vale:** lâmina escoada **não é** vazão, cota nem área inundada.
Entre o escoamento gerado e a água na porta de alguém há caminho, tempo, rede de
drenagem e o nível do corpo receptor — e no RS o receptor costuma ser laguna
governada por vento, onde a água chega e não sai.

---

## 4. Degradação do solo — `degradacao.py`

**Pergunta:** onde o solo está sendo perdido mais rápido?

**Conta:** estrutura da RUSLE, `A = R · K · LS · C · P`, com **P = 1**.

Cada fator é valor de tabela atribuído a classe cartográfica, não medida de
campo: K por ordem de solo (não por ensaio), LS por classe qualitativa de relevo
(não por modelo de elevação), C por uso mapeado a 1:250.000 (não por talhão), R
do total anual (Renard & Freimund), não da intensidade em 30 minutos.

**A decisão que define a camada:** a classe publicada é **posição no estado**,
nunca corte absoluto da literatura. A RUSLE não tem teto em declividade e P = 1
remove a única defesa que existe no campo — em encosta ela devolve centenas de
t/ha/ano, valor que o próprio perfil raso torna impossível de sustentar.
Importar *"50 = alta"* carimbaria metade do estado (ADR-083).

Ao lado do índice viajam os **números medidos**, que sobrevivem à contestação
dele: 70.042 km² sob uso intensivo em relevo declivoso e 37.048 km² de solo raso
sob lavoura — área cruzando duas classes do IBGE, sem tabela nenhuma no meio
(ADR-084).

**Como derrubar:** Wischmeier delimita o domínio da USLE — parcelas de 22 m, no
meio-oeste americano, relevo suave, perda média anual. Encosta de basalto a 45%
está fora. Se a extrapolação for considerada indefensável até para *ordenar*, o
índice sai e ficam as áreas.

**Onde ele não vale:** não é erosão linear (sulco, ravina, voçoroca — o processo
que mais destrói estrada rural no estado), não é movimento de massa (outra
física, com camada própria no geotécnico) e não é série temporal — é retrato do
potencial sob as condições mapeadas.

---

## 5. Condição de umidade antecedente (AMC) — `antecedente.py`

**Pergunta:** qual dos dois Curve Numbers vale **hoje**?

**Conta:** tabela do próprio método, sobre a chuva dos 5 dias anteriores.

| | estação dormente | estação de crescimento |
|---|---|---|
| AMC I (seco) | < 12,7 mm | < 35,6 mm |
| AMC II (média) | 12,7 – 27,9 mm | 35,6 – 53,3 mm |
| AMC III (úmido) | > 27,9 mm | > 53,3 mm |

```
CN1 = 4,2 · CN2 / (10 − 0,058 · CN2)
CN3 = 23 · CN2 / (10 + 0,13 · CN2)
```

**Parâmetros no payload:** janela de 5 dias, meses de crescimento e o limiar
vigente em milímetros.

**A escolha que é nossa:** a estação de crescimento no RS é outubro a abril. A
tabela original não data a estação, porque quem a usava sabia — e no hemisfério
sul a definição desloca o limiar em quase 26 mm: 30 mm em cinco dias é solo
encharcado em julho e apenas condição média em janeiro (ADR-092).

**Como derrubar:** compare com umidade de solo medida (sonda ou satélite de
micro-ondas). Isto é proxy por chuva acumulada, que ignora evapotranspiração,
textura e lençol — dois municípios com a mesma chuva de cinco dias podem estar
em estados bem diferentes, e a tabela não sabe disso.

**Onde ele não vale:** não é previsão. A condição publicada é a de **ontem**, com
chuva observada. Se chover hoje à noite, ela muda amanhã.

---

## 6. Recursos e vazios — `recursos.py`

**Pergunta:** onde estão os meios de resposta, onde falta, e **quais saem de
operação junto com o evento**?

**Conta:** contagem por papel e distância haversine ao mais próximo, a partir do
centroide municipal. A exposição hídrica cruza cada ponto com a célula de ~500 m
do JRC.

**Parâmetros no payload:** limiar de vazio (30 km), limiar de exposição (5% da
célula) e a completude de cada fonte (cadastro / cadastro parcial /
colaborativa).

**O achado, e ele é explicável:** infraestrutura aparece exposta a 13,8% contra
3,5% do suprimento — quatro vezes mais. Não é acaso, é projeto: captação
*precisa* ficar junto do rio, e subestação procura terreno plano e barato, que
na planície é a várzea. **O que mantém a cidade funcionando foi construído onde
a água passa.**

**Como derrubar:** a distância é linha reta, não rota — é um **piso** da
dificuldade de acesso, e em cheia a distância real cresce e às vezes não existe.
E a exposição é da célula de 500 m, não do prédio: sem cota, sem profundidade,
sem defesa. Prédio atrás de dique aparece exposto do mesmo jeito, porque o
satélite viu água ali antes do dique.

**Onde ele não vale:** é base, **nunca viatura**. "Realocar viatura" aqui só pode
significar *onde o vazio é maior diante do risco*; dizer "mova N carros de A para
B" exigiria frota, malha viária e modelo de tempo-resposta.

---

## 7. As outras camadas, em uma linha cada

| Módulo | Pergunta | Selo | Limite dominante |
|---|---|---|---|
| `aguas.py` | onde já foi água e hoje não é? | measured | série termina em 2021 |
| `geotecnico.py` | encosta, travessia e barragem | measured/modeled | ponte é existência, não laudo |
| `pessoal.py` | há quadro para responder? | measured | vínculo declarado ≠ capacidade |
| `resposta.py` | o que falhou em 2024? | measured | auto-declaração ao IBGE |
| `plano.py` | de lacuna nomeada a ação nomeada | modeled | ação é família, não projeto |
| `territorios.py` | quem mora onde a água volta | measured | ausência no mapa ≠ ausência de gente |
| `historico.py` | a chuva de primavera mudou? | measured | série do GHCN termina em 2022 |
| `dossie.py` | tudo de um município, na ordem da decisão | por bloco | não calcula — junta |

---

## 8. O que nenhum modelo aqui faz

- **Prever chuva.** A engine sazonal desloca probabilidade de fundo; não prevê
  evento individual, e o horizonte sinótico está fora de escopo para sempre
  (ADR-013). Maio/2024 foi bloqueio sinótico: nenhuma versão desta engine o
  teria previsto.
- **Dimensionar obra.** Toda a cartografia de base é 1:250.000.
- **Afirmar skill.** Enquanto nenhum modelo passar o critério da ADR-007
  (limite inferior do IC 90% de RPSS > 0), a métrica publicada é `null` — e
  `null` é a resposta correta, não um bug.
