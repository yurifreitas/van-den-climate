# Dados — o que a central sabe, e desde quando

`manifests/sources.yaml` é o catálogo formal, legível por máquina e travado por
teste. Este documento é a versão em prosa: **o que cada fonte responde, quão
atual ela é, e onde ela deixa de valer**.

A ordem não é alfabética nem cronológica. É a ordem em que uma pergunta real
atravessa as fontes: *o que o clima está fazendo* → *o que já aconteceu aqui* →
*no que a chuva cai* → *quem está exposto* → *com o que se responde*.

---

## 0. A regra que organiza tudo

Toda fonte grava, em `data/raw/<id>/<timestamp>/`, o payload byte a byte mais um
`provenance.json` com `url`, `fetched_at`, `sha256`, `product_version` e
`ingestor_version`. O parquet em `data/interim/` é derivado e descartável; o
bruto não.

Isso existe por um motivo específico: **fontes revisam o passado em silêncio.**
O INMET reescreve série histórica, o CNES muda taxonomia, o Overpass reflete
edições de ontem. Sem o bruto datado e com hash, "de onde veio este número" vira
pergunta sem resposta em seis meses.

### Atualidade — a coluna que mais engana

| Fonte | Cobre | Latência real |
|---|---|---|
| CPC ONI / SOI / AAO | 1950– | mês corrente |
| **CPC precipitação diária** | 1979– | **ontem** |
| CNES | cadastro vivo | mês |
| OSM (emergência, recursos) | mapa vivo | dia (edição colaborativa) |
| MUNIC 2024 | evento de 26/04/2024 | fixa, não atualiza |
| GHCN-Daily | 1934–2022 | **congelada** |
| JRC Global Surface Water | 1984–2021 | **congelada** |
| IBGE BDiA (solo, vegetação, relevo) | levantamento por folha | **décadas** |
| Copernicus DEM GLO-90 | altitude/declividade | produto estático (2019) |

A linha que mais importa é a última. Quando a interface mostra fração de solo
ou de cobertura, ela está mostrando um levantamento que pode ser mais velho que
o leitor — e nenhuma dessas camadas ganha um selo diferente por isso. O selo diz
`measured` porque *foi medido*; a data diz quando. As duas informações são
distintas e as duas precisam viajar.

---

## 1. Clima — o que o oceano e a atmosfera estão fazendo

### `cpc_oni`, `cpc_soi`, `cpc_aao`, `psl_nino`
Índices mensais do NOAA. ONI é o estado do ENSO em janela trimestral móvel; SOI
é a assinatura atmosférica do mesmo acoplamento; AAO/SAM é o modo anular do
hemisfério sul, fisicamente distinto do ENSO e não redundante com ele.

**Onde quebra:** ONI muito alto com SOI muito baixo é acoplamento em desacordo,
e a média condicional esconde variância grande entre eventos — a leitura
adversarial de Kug em `manifests/references.yaml` ataca exatamente isso.

### `cpc_enso_advisory`
O boletim mensal do CPC, em prosa. Está no catálogo para que a central mostre
**o que a autoridade oficial está dizendo ao lado do que a engine calcula**, e a
divergência, quando houver, fique visível em vez de escondida.

### `cpc_precip` — a única fonte de chuva *atual*
CPC Global Unified Gauge-Based Analysis: grade de 0,5°, diária, de 1979 até
ontem, por interpolação de **pluviômetros** (não satélite, não modelo).

Fecha o buraco entre a chuva histórica (que termina em 2022) e o oceano do mês
corrente. Sem ela a central não sabia quanto choveu na semana passada, e
portanto não sabia qual dos dois Curve Numbers valia hoje — ver
[MODELOS.md](MODELOS.md#5-condição-de-umidade-antecedente-amc).

**Onde quebra, e é grave:** a célula tem ~55 km, maior que a maioria dos
municípios do RS — até **24 municípios dividem a mesma célula** e não têm
diferença de chuva neste dado. E a célula é média de área: uma tempestade
convectiva de 15 km com 120 mm aparece como ~20 mm espalhados. O produto
subestima o extremo pontual **por construção**, e não substitui estação.

**Duas armadilhas de formato**, ambas silenciosas: o arquivo é NetCDF-4 (o
`scipy` não lê; o GDAL do rasterio lê), e o eixo de tempo vem em **horas** desde
1900. Tratado como dias, devolve uma série completa, ordenada, coerente — e três
mil anos no futuro, sem erro nenhum.

### `inmet_automaticas` — tentada, indisponível
Seria a fonte natural: 98 estações automáticas só no RS, horárias. A API pública
devolve a lista de estações e responde `204 No Content` para qualquer consulta
de **dados**, em toda data testada, com e sem token. O caminho restante é o
BDMEP, que exige login.

Fica no catálogo com `status: tentado_indisponivel` em vez de desaparecer.
Fonte que sumiu do catálogo é fonte que alguém vai propor de novo daqui a seis
meses, e refazer o mesmo teste.

---

## 2. História — o que já aconteceu aqui

### `ghcn_rs`
GHCN-Daily, 66 estações no RS, **1934–2022**. É a série diária mais longa
disponível e a base da chuva de projeto (Gumbel sobre máximos anuais) da camada
hidrológica.

**Onde quebra:** ano de cobertura parcial não pode entrar como máximo anual. O
máximo de um ano com 60 dias observados não é o máximo daquele ano — é o maior
de uma amostra pequena, sistematicamente menor. Misturado aos anos completos,
puxa a distribuição inteira para baixo, e o efeito é pior nas estações urbanas
recentes: Porto Alegre saía com chuva de TR 2 de 32 mm, um terço do plausível.

### `jrc_gsw` — memória hídrica
Global Surface Water (Pekel et al., *Nature* 2016): cada pixel de 30 m
classificado entre 1984 e 2021 como água permanente, sazonal, **perdida** ou
nova. As classes "perdida" e "efêmera" são o achado — terreno que **já foi
água** e hoje não é.

**A limitação é a virtude:** a série termina em 2021 e não contém a cheia de
2024. Quando um município com muita água perdida aparece também com inundação
declarada em 2024, isso é coincidência entre duas bases independentes, não
circularidade.

### `ibge_munic_rs` — MUNIC 2024
497 municípios × ~100 variáveis sobre o evento de 26/04/2024: quais perigos
ocorreram, qual foi o dano e — decisivo — se havia plano de contingência, se foi
executado, e **por que não**.

**Onde quebra:** é auto-declaração da prefeitura ao IBGE. Há incentivo
assimétrico entre relatar dano (atrai recurso) e relatar falha de prevenção
(expõe gestão). E município que não respondeu aparece como lacuna, nunca como
zero — foi o que pôs Bagé em 1º lugar por *não ter respondido* (ADR-019).

---

## 3. Chão — no que a chuva cai

### `ibge_bdia` — pedologia, vegetação e geomorfologia
Três camadas do Banco de Dados de Informações Ambientais, a 1:250.000, servidas
pelo mesmo WFS:

- **pedologia** — ordem SiBCS, textura, relevo local, pedregosidade. Responde
  *esse solo absorve?*
- **vegetação e uso** — fitofisionomia original, vegetação secundária e uso
  antrópico. Responde *o que cobre esse solo hoje?*
- **geomorfologia** — unidade de relevo, forma de topo, **densidade de drenagem**
  e aprofundamento de incisão. Responde *para onde a água vai, e com que pressa?*

E o **cruzamento** das três, célula a célula. Isso não é refinamento: o Curve
Number pergunta o par (solo, cobertura), e com três tabelas ao lado só restaria
supor independência — suposição falsa numa direção conhecida, porque a lavoura
procura o solo profundo e a mata sobra na encosta (ADR-081).

**Onde quebra:** escala. O polígono tem quilômetros de largura; várzea estreita,
afloramento pontual e corte de estrada não aparecem. E o levantamento tem
décadas de defasagem em várias folhas — a camada de uso antrópico é *vocação
consolidada*, não cobertura do ano corrente.

**Três armadilhas de API**, todas silenciosas: `propertyName` sem `geom` devolve
200 com geometria nula em toda feição (o estado sai com zero km²); `bbox` em WFS
2.0 com CRS em URN espera **lat,lon** e a ordem trocada devolve zero feições em
vez de erro; e os rótulos vêm quebrados por linha (`"suave \nondulado"`),
herdados da diagramação da carta impressa.

### `ghsl_built`
GHS-BUILT-S (JRC), época 2025, 30". Metros quadrados de superfície construída
por célula.

**Onde quebra:** é **proxy** de impermeabilização, não medida dela. Não distingue
asfalto de piso drenante, não vê calçada permeável e não vê compactação de solo
agrícola — que impermeabiliza sem construir nada.

### `ana_bacias`
Divisões de bacias do SNIRH. Dá o **regime de cheia** por município: fluvial,
lagunar ou litorâneo. Regime lagunar é o que o vento governa, e onde a drenagem
por gravidade falha justamente quando mais se precisa dela.

### `copernicus_dem` — a declividade medida
GLO-90 (ESA, derivado do TanDEM-X), 43 tiles cobrindo o estado. Substituiu o
adjetivo da carta no fator que mais alavanca o resultado: LS cresce **quarenta
vezes** do plano ao montanhoso, e essa diferença estava sendo decidida por um
rótulo que descreve o polígono inteiro pela feição predominante em área.

Declividade média do estado: **12,7%**; 20,5% da área acima de 20% de
inclinação.

**O achado:** o fator de reancoragem (LS medido ÷ LS da carta) tem mediana
**1,06** — a carta acerta na *média do estado* — mas varia de **0,14 a 2,60**
entre municípios. Ela erra onde a decisão acontece, e isso não apareceria em
nenhuma estatística agregada.

**Onde quebra:** é modelo de **superfície**, não de terreno — mede topo de
dossel e telhado, e em área florestada a declividade sai contaminada pela borda
da mata. A 90 m somem talude de corte, barranca de arroio e degrau de terraço: é
a declividade da encosta, não a do talude.

---

## 4. Gente — quem está exposto

### `ibge_pop_rs`, `ibge_malha_rs`
Estimativa populacional 2024 e a malha municipal. A malha é a base geométrica de
tudo: rasterização, centroide e recorte por município.

### `ibge_quilombola`, `ibge_indigena`
Territórios tradicionais mapeados. **40 no RS**, com 35% em bacia lagunar contra
8% dos municípios do estado — concentração de 4×, histórica e não climática:
terra remanescente é a que sobrou, e a que sobra é a de várzea.

**Onde quebra, e é a ressalva mais importante do catálogo:** ausência de
território mapeado **não é** ausência de comunidade. O viés é sistemático e numa
direção só — quem tem menos acesso a Estado tem menos chance de ter processo
fundiário aberto (ADR-075). E `situacao_juridica` é sempre visível: terra em
estudo e terra homologada são o mesmo polígono e realidades opostas (ADR-076).

---

## 5. Meios — com o que se responde

### `cnes_rs`
Cadastro de estabelecimentos de saúde. Hospital, pronto-socorro, CAPS, unidade
móvel, central de regulação.

**Onde quebra:** é estabelecimento, **nunca leito nem viatura** (ADR-036). A
frota do SAMU opera sob o CNES da central de regulação e não aparece uma a uma —
as 7 centrais são o sinal confiável de cobertura, a contagem de móveis não é. E
o `codigo_tipo_unidade` 43, cujo rótulo diz "Unidade Móvel de Nível
Pré-Hospitalar", devolve **farmácias**: quase quatro mil entrariam no mapa como
ambulância.

### `osm_emergencia`, `osm_recursos`
Do OpenStreetMap, sob ODbL — que **exige atribuição visível** em obra derivada
publicada; é obrigação legal, não cortesia.

`osm_emergencia` traz quartéis, unidades policiais e pontes da malha principal.
`osm_recursos` traz as quatro famílias que 2024 mostrou que faltavam: abrigo
potencial (escola, ginásio, templo), acesso (heliponto, aeródromo),
infraestrutura (subestação, tratamento e reservatório de água) e suprimento
(combustível, supermercado).

**Onde quebra:** base colaborativa — ausência no mapa não prova ausência no
território, e a cobertura é pior no interior, que é também onde há menos recurso
real: **o viés empurra na direção errada**. Para ponte, é existência e nunca
estado de conservação. E **abrigo é potencial, jamais cadastro**: um ginásio é um
prédio grande e coberto, sem capacidade, banheiro, cozinha ou gerador
declarados, e a lista real é da Defesa Civil municipal, que não publica
(ADR-086).

### `ana_telemetria` — mapeada, não ingerida
Nível e vazão de rio em tempo quase real, por SOAP público e sem chave. É o
insumo que falta para **calibrar** o Curve Number: hoje a camada hidrológica é
tabela aplicada, e nenhum número dela foi confrontado com água medida passando.

---

## 6. O que fazer quando uma fonte cai

Fonte fora do ar não derruba o pipeline: vira **lacuna declarada**. Cada camada
de risco levanta `FileNotFoundError` com a instrução de qual ingestor rodar, a
API responde 503 com a mesma mensagem, e a interface mostra estado de erro em
vez de tabela vazia.

O que **não** pode acontecer, e é o que os testes perseguem: fonte ausente virar
zero. Zero afirma medição; ausência é ausência. Toda camada que agrega usa
`None` para "não medido" e reserva `0` para "medido e deu zero".
