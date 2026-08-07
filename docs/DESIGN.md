# Sistema de design — Central de Risco Climático RS

Referência única para `web/`. Se um valor não está aqui, ele não deve estar
hard-coded num componente.

O alvo não é "bonito". É **instrumento de leitura**: alguém decide com base
nisto. Elegância aqui é densidade sem ruído, hierarquia legível de longe, e
zero ornamento competindo com o dado.

---

## 1. Cor

### Superfícies e tinta (interface)

| Token | Valor | Uso |
|---|---|---|
| `--abissal` | `#0F1518` | fundo da aplicação |
| `--carta` | `#151E23` | superfície de painel (elevação 1) |
| `--carta-alta` | `#1B2429` | elevação 2 — cabeçalho fixo, linha ativa |
| `--linha` | `#243139` | borda hairline, divisor de tabela |
| `--grade` | `#1E2A31` | gridline de gráfico (um passo acima da superfície) |
| `--giz` | `#D8DEE0` | tinta primária |
| `--bruma` | `#8A979E` | tinta secundária, eixos, rótulos |
| `--bruma-fraca` | `#5E6B72` | tinta terciária, nota de rodapé |

### Dado (e **somente** dado)

| Token | Valor | Uso |
|---|---|---|
| `--frio` | `#2B8FD6` | anomalia negativa |
| `--quente` | `#C1553A` | anomalia positiva |
| ponto médio | `--bruma-fraca` neutro | o meio da escala divergente **não tem matiz** |

O `--frio` mudou de `#3E7FA8` para `#2B8FD6`: o valor antigo reprovou no
teste de croma do validador (0,092 — lê como cinza sobre a superfície escura).
O novo par passa nas seis verificações, com ΔE 22,7 no pior caso sob CVD
(deuteranopia) e ΔE 27,9 em visão normal.

**Regra inviolável**: nenhum elemento de interface usa `--frio`/`--quente`.
Botão, foco, link, estado ativo, selo — tudo em giz/bruma. Assim, cor na tela
significa sempre anomalia. Há teste que falha se isso for violado.

**Texto nunca veste a cor do dado.** Identidade vem da marca colorida *ao lado*
do texto, nunca do texto colorido.

---

## 2. Tipografia

Escala modular, razão 1,2. Tudo em `rem`.

| Token | Tamanho | Peso / família | Uso |
|---|---|---|---|
| `--t-display` | 1.75rem | Archivo Expanded 700, uppercase, `letter-spacing: .06em` | título de visão |
| `--t-section` | 0.8125rem | Archivo Expanded 600, uppercase, `.12em` | título de painel |
| `--t-body` | 0.9375rem | Inter Tight 400 | corpo |
| `--t-small` | 0.8125rem | Inter Tight 400 | secundário |
| `--t-note` | 0.75rem | Inter Tight 400 | nota de rodapé, limitações |
| `--t-data` | 0.875rem | IBM Plex Mono 400, `tabular-nums` | todo número |
| `--t-hero` | 2.5rem | IBM Plex Mono 500, `tabular-nums` | número-manchete |

`font-variant-numeric: tabular-nums` é **obrigatório** em toda tabela, eixo e
valor. Dígito que dança entre linhas destrói a leitura de coluna.

Altura de linha: 1.5 no corpo, 1.25 em títulos, 1 em números grandes.

---

## 3. Espaço e ritmo

Escala: **4 / 8 / 12 / 16 / 24 / 32 / 48 / 64**. Nada fora dela.

- Largura máxima de leitura: **1200px**, centralizada, `padding: 0 24px`.
- Painel: `padding: 20px 24px`, `border: 1px solid var(--linha)`,
  `border-radius: 3px`. Raio pequeno — instrumento, não cartão de app.
- Distância entre painéis: 24px. Entre grupos de visão: 48px.
- Densidade de tabela: linha de 40px, `padding: 0 16px`.

**Sem sombra.** Elevação por superfície e borda hairline, nunca por blur —
sombra em tema escuro vira sujeira.

---

## 4. Estrutura da página

```
┌ cabeçalho fixo (56px, --carta-alta, borda inferior) ──────────────┐
│  marca            nav (7 rotas)                estado: ONI +1.39  │
└───────────────────────────────────────────────────────────────────┘
┌ conteúdo, max 1200px ─────────────────────────────────────────────┐
│  título da visão + uma linha do que ela responde                  │
│  painéis                                                          │
└───────────────────────────────────────────────────────────────────┘
```

O indicador de estado no cabeçalho é permanente: numa central de risco, o
estado corrente nunca deve exigir navegação.

---

## 5. Gráficos

Especificações fixas, do guia de visualização:

| Marca | Spec |
|---|---|
| Barra | ≤ 24px de espessura, **nunca preencher a faixa**; ponta arredondada 4px, quadrada na base |
| Linha | 2px, junta e ponta arredondadas |
| Marcador | ≥ 8px de diâmetro, com anel de 2px na cor da superfície |
| Preenchimento de área | matiz da série a ~10–14% de opacidade — lavagem, nunca bloco |
| Gridline | 1px sólida, `--grade`, recessiva. **Nunca tracejada** |
| Separação entre marcas | **gap de 2px na cor da superfície**, nunca contorno |

Regras que valem aqui especificamente:

- **Um eixo, sempre.** Nada de dois eixos y. ONI e SAM são duas cartas, nunca
  uma sobreposta.
- **Janela padrão de 20 anos** nas séries longas, com controle para expandir.
  Na série completa (1950–) a banda divergente some por densidade — foi o
  defeito observado.
- **Legenda presente com 2+ séries**; série única não leva legenda (o título
  já a nomeia).
- **Rótulo direto seletivo** — no extremo e no último ponto, nunca em todos.
- **Camada de hover por padrão**: crosshair + tooltip em linha/área, tooltip
  por marca em barra/célula.
- Valor ausente é **"—"**, nunca 0, nunca gráfico quebrado.

---

## 6. Estado e movimento

- Carregamento: **esqueleto** na cor `--carta-alta`, sem pulso. Nunca spinner.
- Vazio: frase do que falta + o que destrava. Nunca ilustração.
- Erro: o que falhou e o que ainda é confiável. Nunca tela branca.
- Movimento apenas entre estados temporais. `prefers-reduced-motion`
  respeitado — e **gráfico nunca depende de animação para renderizar**
  (barra presa em altura zero foi defeito real).

---

## 7. Acessibilidade — piso, não extra

- Foco visível: contorno 2px `--giz`, offset 2px. Nunca `outline: none`.
- Contraste mínimo 4,5:1 em texto; 3:1 em marca de dado.
- Identidade nunca só por cor: legenda + rótulo + tabela.
- Toda visão de gráfico oferece a tabela equivalente.
- Alvo de toque ≥ 44px em mobile.

---

## 8. Como o sistema escala — camada de primitivas

Tokens sozinhos não seguram um sistema: cada visão remonta a casca à mão e
deriva um pouco. O contrato de composição vive em `web/src/components/ui/`.

**Camadas, de baixo para cima:**

| Camada | Arquivo | Responsabilidade |
|---|---|---|
| Tokens | `theme/tokens.css` | valores brutos: cor de interface, espaço, tipo |
| Cor de dado | `theme/chartColors.ts` | `--frio`/`--quente`, isolados (§1) |
| Primitivas | `components/ui/` | layout e estrutura: `View` `Section` `Panel` `Grid` `Stack` `Row` `Metric` `Field` `Empty` `DataTable` |
| Componentes de domínio | `components/` | `HazardCard`, `TercileChart`, `ProvenanceBadge`, … |
| Visões | `views/` | só composição + dados. Sem CSS de layout |

**Regras duras:**

1. Visão é `<View title intro actions>`; nunca `<section className="view">`.
2. Painel é `<Panel>`; nunca `<div className="panel">`.
3. Tabela é `<DataTable columns rows>` — rolagem, cabeçalho fixo, zebra,
   `tabular-nums`, ordenação e `aria-sort` num lugar só.
4. Espaço só via `gap` das primitivas (escala 1/2/3/4/6/8/12). `style` de
   layout numa visão é sinal de primitiva faltando — adicione em `ui/`.
5. Nenhuma primitiva aceita cor como prop. Cor é exclusividade do dado.
6. Número ausente é `—`: `<Metric>` já faz isso, e coluna de `DataTable`
   deve devolver `—`, nunca `0`.

**Referências do padrão** (por que primitivas e não uma biblioteca pronta):
primitivas de layout com ritmo vertical vivendo no `Stack`
([Design System Primitives](https://codercarl.dev/blog/design-system/primitives)),
organização por `shared/ui` + fatias verticais
([React System Design & Architecture 2026](https://qcode.in/react-system-design-architecture-the-complete-2026-guide/)),
e a estratégia de token em três níveis — primitivo → semântico → camada de
gráfico com escala categórica/sequencial/divergente — que é exatamente a
separação `tokens.css` / `chartColors.ts` adotada aqui
([Design system examples 2026](https://designsystems.surf/articles/11-best-design-system-examples-in-2026)).
Bibliotecas de dashboard (Ant Design, Tremor) foram descartadas: trazem
paleta e cartão de app próprios, que colidem com a regra §1 — cor na tela
significa anomalia, e nada mais.
