# Documentação — o mapa

Sete documentos, cada um com um leitor em mente. Se você está procurando um
número específico, comece pelo último item da lista: quase toda pergunta
concreta termina num ADR.

| Documento | Responde | Leia se você vai |
|---|---|---|
| [../README.md](../README.md) | o que é isto e como rodar | chegar pela primeira vez |
| [ARCHITECTURE.md](ARCHITECTURE.md) | como o dado entra e por onde passa | escrever um ingestor |
| [DADOS.md](DADOS.md) | o que cada fonte responde e onde deixa de valer | usar um número |
| [MODELOS.md](MODELOS.md) | o que cada modelo afirma e como derrubá-lo | contestar um resultado |
| [API_CONTRACT.md](API_CONTRACT.md) | a fronteira entre back e front | consumir a API |
| [DESIGN.md](DESIGN.md) | as regras visuais e por que existem | mexer na interface |
| [LAYER2_QUALITY.md](LAYER2_QUALITY.md) | homogeneização e qualidade de série | mexer na Camada 2 |
| [../manifests/decisions.md](../manifests/decisions.md) | **toda decisão, datada, com a razão** | entender por que algo é assim |

---

## A ordem em que isto foi construído, e por quê

A central não nasceu como central. Nasceu como engine de previsão sazonal com
n=36, e o pivô para risco climático (ADR-013) mudou o que conta como sucesso —
mas não afrouxou nenhuma das regras que a fase anterior tinha imposto. É por
isso que uma camada de recursos de emergência carrega selo de proveniência: a
disciplina veio de um lugar onde ela era questão de sobrevivência estatística.

```
        CLIMA                    TERRITÓRIO                  RESPOSTA
   ONI · SOI · SAM          solo · vegetação · relevo    saúde · bombeiro
   chuva histórica          memória hídrica              abrigo · energia
   chuva de ontem           superfície construída        água · suprimento
        │                          │                            │
        └──────────┬───────────────┴────────────┬───────────────┘
                   ▼                            ▼
            balanço de chuva              índice de prioridade
            degradação do solo            contenção · plano
                   │                            │
                   └────────────┬───────────────┘
                                ▼
                        dossiê municipal
                   (junta, não calcula — e declara
                    o que cada camada não sabe)
```

---

## As cinco regras que atravessam tudo

Estão no `CLAUDE.md` em forma curta. Aqui, com a razão:

1. **Toda feature declara a defasagem no nome** (`oni_lag3_son`, nunca `oni`).
   Sem isso, vazamento temporal vira uma edição de uma linha que ninguém revisa.

2. **Todo número derivado carrega `provenance.basis`.** Número sem selo é bug.
   A tentação recorrente é lavar procedência por origem — *"veio de um mapa
   oficial, logo é medido"*. Ver [MODELOS.md §0](MODELOS.md#0-a-fronteira-que-atravessa-todos).

3. **Nível de risco derivado de heurística não é `measured`.** Enquanto nenhum
   modelo passar a ADR-007, é `modeled` e carrega o próprio limite.

4. **O perigo sinótico aparece no catálogo com `level: null`**, nunca omitido.
   Maio/2024 foi sinótico; uma central que some com a linha comunica mais
   confiança do que tem.

5. **`FRIO`/`QUENTE` pertencem exclusivamente ao dado.** Nenhum elemento de
   interface usa essas cores — e é por isso que o mapa de recursos colore por
   família, não por papel: o categórico tem seis cores e não cicla.

---

## Como a documentação é mantida honesta

`tests/test_docs.py` trava quatro invariantes, e cada um corresponde a uma forma
já observada de a documentação apodrecer:

- **toda rota registrada na API aparece em `API_CONTRACT.md`** — onze rotas
  viveram meses com a razão de existir só na docstring do módulo;
- **todo ingestor tem entrada em `sources.yaml`** — o catálogo formal ficou
  incompleto enquanto cada ingestor documentava a própria fonte internamente;
- **todo módulo de risco aparece em `MODELOS.md`** — camada sem limite escrito
  é camada que alguém vai citar sem a ressalva;
- **todo ADR citado nos documentos existe** de fato na tabela.

Documentação que não pode falhar em CI não é contrato, é intenção.
