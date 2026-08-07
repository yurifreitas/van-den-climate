"""Snapshot estatico — a demo do GitHub Pages.

O teste central aqui e `test_slug_python_e_typescript_concordam`.

O gerador (Python) escolhe o nome de cada arquivo; o cliente (TypeScript)
calcula o nome que vai pedir. Sao duas implementacoes da MESMA funcao, em
linguagens diferentes, em arquivos diferentes. Se divergirem, nada quebra no
build, nada quebra em dev com backend, nada quebra nos testes de front — e a
demo publica pede um arquivo que nao existe. O bug aparece so em producao,
que e o pior lugar possivel.

Como nao da para importar TypeScript aqui, o teste le o `.ts` e verifica que
as regras de transformacao continuam as mesmas. E frouxo de proposito: um
teste que exigisse o arquivo identico quebraria a cada comentario.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.build_static_snapshot import ROTAS, SAIDA, slug

REPO_ROOT = Path(__file__).resolve().parents[1]
CLIENT_TS = REPO_ROOT / "web" / "src" / "api" / "client.ts"


# ---------------------------------------------------------------------------
# A regressao que este arquivo existe para impedir
# ---------------------------------------------------------------------------
def test_slug_python_e_typescript_concordam():
    """As duas implementacoes precisam aplicar as mesmas quatro regras."""
    ts = CLIENT_TS.read_text(encoding="utf-8")
    trecho = ts[ts.index("export function slugEstatico") : ts.index("export function assetUrl")]

    # 1. tira a barra inicial; 2. troca '/' por '_'
    assert "replace(/^\\//, '')" in trecho
    assert "replace(/\\//g, '_')" in trecho
    # 3. parametros em ordem alfabetica
    assert ".sort()" in trecho
    # 4. separador '~chave-valor' e sanitizacao igual a do Python
    assert "~${chave}-${" in trecho
    assert "replace(/[^A-Za-z0-9]+/g, '-')" in trecho
    # e o mesmo descarte de parametro ausente
    assert "=== undefined) continue" in trecho


@pytest.mark.parametrize(
    ("path", "params", "esperado"),
    [
        ("/meta", None, "meta"),
        ("/series/oni", None, "series_oni"),
        ("/forecast/OND2026/attribution", None, "forecast_OND2026_attribution"),
        ("/risk/municipal", {"cenario": "ond2026"}, "risk_municipal~cenario-ond2026"),
        ("/risk/municipal/cruzamento/aguas", {"limit": 30}, "risk_municipal_cruzamento_aguas~limit-30"),
        # ordem alfabetica, nao ordem de insercao
        ("/x", {"b": 2, "a": 1}, "x~a-1~b-2"),
        # parametro ausente nao entra na chave
        ("/x", {"a": 1, "b": None}, "x~a-1"),
        # sanitizacao de caractere fora de [A-Za-z0-9]
        ("/x", {"q": "a b/c"}, "x~q-a-b-c"),
        ("/geo/aguas.png", None, "geo_aguas.png"),
    ],
)
def test_slug_casos(path, params, esperado):
    assert slug(path, params) == esperado


# ---------------------------------------------------------------------------
# Integridade do snapshot gerado
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def manifesto():
    path = SAIDA / "_manifest.json"
    if not path.exists():
        pytest.skip("snapshot nao gerado — rode `python -m scripts.build_static_snapshot`")
    return json.loads(path.read_text(encoding="utf-8"))


def test_todo_arquivo_do_manifesto_existe(manifesto):
    for rota in manifesto["rotas"]:
        assert (SAIDA / rota["arquivo"]).exists(), f"faltando {rota['arquivo']}"


def test_manifesto_cobre_todas_as_rotas_declaradas(manifesto):
    """Se alguem adicionar uma rota em ROTAS e nao rodar o gerador, pega aqui."""
    no_manifesto = {(r["path"], json.dumps(r["params"], sort_keys=True)) for r in manifesto["rotas"]}
    for path, params in ROTAS:
        chave = (path, json.dumps(params, sort_keys=True))
        assert chave in no_manifesto, f"rota nao congelada: {path} {params}"


def test_toda_resposta_carrega_a_data_da_captura(manifesto):
    """Numero congelado sem data e o que esta demo nao pode publicar."""
    for rota in manifesto["rotas"]:
        arquivo = SAIDA / rota["arquivo"]
        if arquivo.suffix != ".json" or arquivo.name == "_manifest.json":
            continue
        corpo = json.loads(arquivo.read_text(encoding="utf-8"))
        if isinstance(corpo, dict):
            assert corpo.get("_snapshot", {}).get("capturado_em"), f"{arquivo.name} sem carimbo"


def test_snapshot_tem_os_tres_cenarios(manifesto):
    nomes = {r["arquivo"] for r in manifesto["rotas"]}
    for c in ("atual", "ond2026", "estrutural"):
        assert f"risk_municipal~cenario-{c}.json" in nomes


def test_overlay_de_agua_foi_copiado(manifesto):
    assert (SAIDA / "geo_aguas.png").exists()


def test_faixa_de_demo_declara_o_modo_estatico():
    """A interface tem de avisar; sem isso o snapshot vira numero mentiroso."""
    layout = (REPO_ROOT / "web" / "src" / "components" / "Layout.tsx").read_text(encoding="utf-8")
    assert "MODO_ESTATICO" in layout
    assert re.search(r"Demo\s+estatica", layout)
