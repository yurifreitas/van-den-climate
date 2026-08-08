"""Dossie municipal — a juncao das dez camadas.

O risco proprio deste modulo nao e calculo: ele nao calcula nada. E
**agregacao silenciosa**. Ao reunir dez camadas numa resposta so, tres
falhas ficam faceis de cometer e dificeis de ver:

  1. o dossie carimba um selo unico e apaga a diferenca entre medido,
     modelado e ausente (os testes de basis por bloco);
  2. uma camada faltando vira zero em vez de ausente (test_ausente_nunca_zero);
  3. o bloco 7 encolhe quando alguem "limpa" o payload — e um dossie sem
     lacunas declaradas mente por omissao (test_lacunas_*).

O terceiro e o que este arquivo existe para travar.
"""
from __future__ import annotations

import pytest

from src.risk import dossie, municipal

PORTO_ALEGRE = 4314902


@pytest.fixture(scope="module")
def d():
    if not municipal.MUNIC_PARQUET.exists():
        pytest.skip("MUNIC ausente — rode a ingestao")
    return dossie.build(PORTO_ALEGRE).dados


def test_municipio_inexistente_levanta(_=None):
    if not municipal.MUNIC_PARQUET.exists():
        pytest.skip("MUNIC ausente")
    # Codigo de Sao Paulo capital: existe no Brasil, nao no RS.
    with pytest.raises(KeyError):
        dossie.build(3550308)


def test_sete_blocos_na_ordem_da_decisao(d):
    """A ordem E o conteudo: o dossie e uma sequencia, nao um saco de campos."""
    esperado = ["posicao", "perigo", "exposicao", "capacidade", "falhas_2024", "acao", "lacunas"]
    presentes = [k for k in d if k in esperado]
    assert presentes == esperado


def test_nao_ha_selo_unico_no_topo(d):
    """Selo unico no dossie apagaria a diferenca entre as camadas.

    A proveniencia mora em cada bloco. Se alguem promover um `basis` para a
    raiz do dossie, este teste cai — de proposito.
    """
    assert "basis" not in d


def test_cada_camada_carrega_o_proprio_selo(d):
    assert "basis" in d["posicao"]
    for chave in ("geotecnico", "acesso", "barragem", "memoria_hidrica"):
        bloco = d["perigo"][chave]
        assert bloco is None or "basis" in bloco, chave


def test_ausente_nunca_vira_zero(d):
    """Camada nao ingerida some como None; nunca como 0, 0.0 ou lista falsa.

    O numero zero num painel de risco le como "medimos e deu nada". Ausencia
    le como "nao sabemos". Sao decisoes opostas.
    """
    for chave in ("geotecnico", "acesso", "barragem", "memoria_hidrica"):
        bloco = d["perigo"][chave]
        if bloco is None:
            continue
        for k, v in bloco.items():
            # bool nao entra: `False` aqui significa "declarou que nao houve",
            # que e resposta, nao ausencia. So o zero NUMERICO e suspeito.
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            assert v != 0 or k.startswith("n_"), (chave, k)


def test_ranking_e_coerente_com_a_tabela(d):
    tabela = municipal.build_table(None, "atual")
    com_score = [r for r in tabela.rows if r["score"] is not None]
    assert d["posicao"]["de"] == len(com_score)
    if d["posicao"]["posicao_no_ranking"] is not None:
        assert 1 <= d["posicao"]["posicao_no_ranking"] <= d["posicao"]["de"]
        i = d["posicao"]["posicao_no_ranking"] - 1
        assert tabela.rows[i]["cod_mun"] == PORTO_ALEGRE


def test_lacunas_nunca_vazias(d):
    """Nao existe municipio sobre o qual esta central saiba tudo.

    Se este teste cair com lista vazia, a causa provavel nao e progresso na
    ingestao — e alguem ter parado de propagar `LACUNAS` das camadas.
    """
    assert len(d["lacunas"]) >= 3
    for l in d["lacunas"]:
        assert set(l) >= {"camada", "id", "titulo", "motivo"}
        assert l["motivo"].strip(), l["id"]


def test_lacuna_de_conservacao_de_ponte_sempre_aparece(d):
    """2.159 travessias, zero laudo publico. Nenhum municipio escapa disso."""
    ids = {l["id"] for l in d["lacunas"]}
    assert "conservacao_ponte" in ids or d["capacidade"]["pontes"] is None


def test_acao_nao_inventa_quando_nao_ha_dado(d):
    """Toda acao traz a linha do dado que a disparou — nenhuma e inferida."""
    for a in d["acao"]["acoes"]:
        assert a["evidencia"].strip()
    assert d["acao"]["n_acoes"] == len(d["acao"]["acoes"])
    assert d["acao"]["n_imediatas"] <= d["acao"]["n_acoes"]


def test_estrategia_de_contencao_sempre_traz_o_par_e_o_limite(d):
    """SbN nunca aparece sozinha: sem o par e sem o limite, vira propaganda."""
    for e in d["acao"]["estrategias_contencao"]:
        assert e["convencional"].strip()
        assert e["natureza"].strip()
        assert e["quando_natureza_ganha"].strip()
        assert e["limite"].strip(), e["id"]


def test_territorio_traz_situacao_juridica(d):
    """Territorio sem situacao juridica no painel convida a tratar terra em
    estudo como terra homologada — que e um erro caro."""
    for t in d["exposicao"]["territorios_tradicionais"]:
        assert t["tipo"] in {"territorio quilombola", "terra indigena"}
        assert "situacao_juridica" in t
    assert d["exposicao"]["n_territorios"] == len(d["exposicao"]["territorios_tradicionais"])
