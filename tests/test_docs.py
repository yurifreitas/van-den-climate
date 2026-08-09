"""Documentacao travada por teste.

Cada invariante aqui corresponde a uma forma JA OBSERVADA de a documentacao
apodrecer neste repositorio — nenhuma e hipotetica:

  1. **Rota sem contrato.** Onze rotas (`/terreno`, `/contencao`, `/dossie`,
     `/recursos`, `/pessoal`, `/geotecnico`, `/territorios`, `/plano`,
     `/resposta/municipios`, `/historico/chuva`, `/references`) viveram meses
     com a razao de existir escrita so na docstring do modulo. O contrato
     afirmava cobertura que nao tinha, que e pior que nao existir.

  2. **Ingestor fora do catalogo.** `manifests/sources.yaml` se apresenta como
     o registro de fontes, e onze ingestores nao estavam nele — cada um
     documentava a propria fonte internamente e ninguem voltava ao catalogo.

  3. **Camada sem limite escrito.** Um modulo de risco que nao aparece em
     MODELOS.md e um modulo que alguem vai citar sem a ressalva. Neste projeto
     a ressalva costuma ser metade do resultado.

  4. **ADR fantasma.** Documento que cita "(ADR-077)" com autoridade e aponta
     para uma linha que nao existe e pior que documento sem citacao nenhuma.

Documentacao que nao pode falhar em CI nao e contrato, e intencao.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
DOCS = RAIZ / "docs"
DECISIONS = RAIZ / "manifests" / "decisions.md"
SOURCES = RAIZ / "manifests" / "sources.yaml"


def _texto(*caminhos: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in caminhos if p.exists())


@pytest.fixture(scope="module")
def docs_todos() -> str:
    return _texto(RAIZ / "README.md", *sorted(DOCS.glob("*.md")))


# ---------------------------------------------------------------------------
# 1. Rotas
# ---------------------------------------------------------------------------
def _rotas_registradas() -> set[str]:
    from api.main import app

    saida = set()
    for r in app.routes:
        caminho = getattr(r, "path", "")
        if not getattr(r, "methods", None) or not caminho.startswith("/api/v1"):
            continue
        # `/api/v1/dossie/{cod_mun}` -> `/dossie` — o contrato documenta a
        # familia de rota, nao cada parametro de caminho.
        limpo = caminho.replace("/api/v1", "").split("/{")[0]
        if limpo:
            saida.add(limpo)
    return saida


def test_toda_rota_esta_no_contrato():
    contrato = (DOCS / "API_CONTRACT.md").read_text(encoding="utf-8")
    faltando = sorted(r for r in _rotas_registradas() if r not in contrato)
    assert not faltando, (
        f"rotas registradas e ausentes de docs/API_CONTRACT.md: {faltando}. "
        "Contrato incompleto afirma cobertura que nao tem."
    )


def test_contrato_nao_documenta_rota_inexistente():
    """A outra direcao: rota removida do codigo e mantida no contrato."""
    contrato = (DOCS / "API_CONTRACT.md").read_text(encoding="utf-8")
    registradas = _rotas_registradas()
    # So checa as que aparecem em bloco de codigo com verbo HTTP, para nao
    # capturar mencao em prosa.
    # O ponto entra no padrao por causa de `/geo/aguas.png`: sem ele o regex
    # corta no ponto e acusa uma rota fantasma que so existe no proprio regex.
    citadas = set(re.findall(r"^GET (/[\w/{}.]+)", contrato, re.M))
    fantasmas = sorted(
        c.split("?")[0].split("/{")[0]
        for c in citadas
        if c.split("?")[0].split("/{")[0] not in registradas
    )
    assert not fantasmas, f"contrato cita rota que nao existe mais: {fantasmas}"


# ---------------------------------------------------------------------------
# 2. Fontes
# ---------------------------------------------------------------------------
# Modulos de `src/ingest/` que sao infraestrutura, nao fonte.
NAO_SAO_FONTE = {"base", "cli", "registry"}

# Ingestor -> id(s) de fonte no catalogo, quando o nome do arquivo nao bate.
# Um ingestor pode alimentar varias fontes (o do IBGE baixa malha, MUNIC e
# populacao) e a lista deixa isso explicito em vez de esconder num regex.
ALIAS_FONTE = {
    "ibge_rs": {"ibge_malha_rs", "ibge_munic_rs", "ibge_pop_rs"},
    "territorios": {"ibge_quilombola", "ibge_indigena"},
    "osm_emergencia": {"osm_emergencia"},
    "psl_nino": {"psl_nino"},
}


@pytest.fixture(scope="module")
def fontes() -> dict:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["sources"]


def test_todo_ingestor_tem_fonte_no_catalogo(fontes):
    modulos = {
        p.stem for p in (RAIZ / "src" / "ingest").glob("*.py")
        if not p.stem.startswith("_") and p.stem not in NAO_SAO_FONTE
    }
    faltando = []
    for m in sorted(modulos):
        esperados = ALIAS_FONTE.get(m, {m})
        if not (esperados & set(fontes)):
            faltando.append(m)
    assert not faltando, (
        f"ingestores sem entrada em manifests/sources.yaml: {faltando}. "
        "Catalogo incompleto e pior que catalogo ausente."
    )


def test_fonte_ingerida_declara_os_proprios_perigos(fontes):
    """Fonte `core` sem `hazards` nem `note` e fonte que parece simples.

    Nenhuma e. As que pareciam custaram um dia de depuracao cada: geometria
    nula no WFS, eixo de tempo em horas, farmacia classificada como ambulancia.
    """
    magros = [
        fid for fid, f in fontes.items()
        if isinstance(f, dict) and f.get("status") == "core"
        and not f.get("hazards") and not f.get("note")
    ]
    assert not magros, f"fonte core sem `hazards` nem `note`: {magros}"


# ---------------------------------------------------------------------------
# 3. Modelos
# ---------------------------------------------------------------------------
# Modulos de `src/risk/` que sao utilitario compartilhado, nao camada.
NAO_SAO_CAMADA: set[str] = set()


def test_toda_camada_de_risco_esta_documentada():
    modelos = (DOCS / "MODELOS.md").read_text(encoding="utf-8")
    modulos = {
        p.stem for p in (RAIZ / "src" / "risk").glob("*.py")
        if not p.stem.startswith("_") and p.stem not in NAO_SAO_CAMADA
    }
    faltando = sorted(m for m in modulos if f"{m}.py" not in modelos)
    assert not faltando, (
        f"camadas de risco ausentes de docs/MODELOS.md: {faltando}. "
        "Camada sem limite escrito e camada citada sem a ressalva."
    )


def test_modelos_dizem_como_derrubar_cada_um():
    """O que separa modelo de opiniao com decimais."""
    modelos = (DOCS / "MODELOS.md").read_text(encoding="utf-8")
    assert modelos.count("Como derrubar") >= 5


# ---------------------------------------------------------------------------
# 4. ADRs
# ---------------------------------------------------------------------------
def test_todo_adr_citado_existe(docs_todos):
    tabela = DECISIONS.read_text(encoding="utf-8")
    existentes = set(re.findall(r"^\| (\d{3}) \|", tabela, re.M))
    citados = set(re.findall(r"ADR-(\d{3})", docs_todos))
    fantasmas = sorted(citados - existentes)
    assert not fantasmas, f"documentos citam ADR inexistente: {fantasmas}"


def test_adr_nao_repete_numero():
    tabela = DECISIONS.read_text(encoding="utf-8")
    numeros = re.findall(r"^\| (\d{3}) \|", tabela, re.M)
    repetidos = sorted({n for n in numeros if numeros.count(n) > 1})
    assert not repetidos, f"ADR com numero repetido: {repetidos}"


def test_indice_da_documentacao_lista_todos_os_documentos():
    """docs/README.md e o mapa. Mapa que esquece uma sala nao serve."""
    indice = (DOCS / "README.md").read_text(encoding="utf-8")
    faltando = [
        p.name for p in sorted(DOCS.glob("*.md"))
        if p.name != "README.md" and p.name not in indice
    ]
    assert not faltando, f"documentos fora do indice docs/README.md: {faltando}"
