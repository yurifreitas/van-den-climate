# Instruções do projeto — Central de Risco Climático RS

## Git

**NUNCA adicionar `Co-Authored-By: Claude` (ou qualquer trailer de coautoria de
IA) em mensagens de commit.** Vale para todo commit, sem exceção, inclusive os
feitos por subagentes. A autoria do repositório é do dono do projeto.

Idem para PRs: nada de "🤖 Generated with Claude Code" no corpo.

## Portas

Nunca usar portas padrão — elas colidem com outros projetos abertos e o sintoma
é enganoso (o front sobe e conversa com a API errada).

| Serviço | Porta |
|---|---|
| API FastAPI | 8437 |
| Front Vite | 5931 |
| Streamlit (debug interno) | 8601 |

Subir tudo: `.\run.ps1`

## Regras de engenharia herdadas dos ADRs

Ver `manifests/decisions.md`. As que mais afetam código do dia a dia:

1. Toda feature declara a defasagem no nome (`oni_lag3_son`, nunca `oni`).
2. Todo payload de API com número derivado carrega `provenance.basis`
   (measured | modeled | synthetic). Número sem selo é bug.
3. Nível de risco derivado de heurística **não** é `measured`. Enquanto nenhum
   modelo passar a ADR-007, é `modeled` e carrega o próprio limite.
4. O perigo sinótico aparece no catálogo com `level: null` — nunca omitido.
5. `FRIO`/`QUENTE` pertencem exclusivamente ao dado. Nenhum elemento de
   interface usa essas cores.
6. Mock (MSW) exige opt-in explícito. O padrão é dado real.
