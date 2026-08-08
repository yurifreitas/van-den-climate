"""Modelo hidrologico — o que precisa ser verdade para o CN significar algo.

Tres classes de defeito que este arquivo persegue:

  1. **A armadilha de substring.** "PECUARIA" esta dentro de "AGROPECUARIA".
     Com os testes de classificacao na ordem errada, o mosaico que cobre tres
     quartos do estado caia na linha de pastagem e o CN mediano do RS
     despencava dez pontos — sem erro, sem excecao, sem nada no caminho
     acusando. Foi encontrado comparando o resultado com o mapa, nao com o
     codigo.

  2. **Inversao da tabela brasileira.** No SiBCS, Latossolo muito argiloso e
     grupo A (estrutura granular, alta condutividade) enquanto a intuicao
     vinda da tabela americana diria D por ser argila. Errar esse sinal
     inverte o planalto inteiro.

  3. **Numero sem o proprio limite.** A camada e quase toda modelada, e o
     payload existe para dizer isso. Um `limites` vazio aqui e mais grave que
     um CN errado: o CN errado alguem contesta, a ausencia de limite nao.
"""
from __future__ import annotations

import pytest

from src.risk import hidrologia as h


# ---------------------------------------------------------------------------
# Classificacao de cobertura
# ---------------------------------------------------------------------------
def test_agropecuaria_nao_cai_em_pastagem():
    """A armadilha de substring, travada para sempre."""
    assert h.classe_cobertura("Agropecuaria", "Agropecuaria") == "agropecuaria"
    assert h.classe_cobertura("Agropecuária", "Agropecuária") == "agropecuaria"
    # E o inverso continua funcionando: pecuaria de verdade e pastagem.
    assert h.classe_cobertura("Pecuaria (pastagens)", "Pecuaria (pastagens)") == "pastagem"


def test_uso_antropico_vence_fitofisionomia():
    """O mapa traz a vegetacao que HAVIA junto do uso que a substituiu."""
    assert h.classe_cobertura("Floresta Ombrofila Mista Montana", "Agricultura com Culturas Ciclicas") == "agricultura"


@pytest.mark.parametrize(
    "legenda,uso,esperado",
    [
        ("Corpo d'agua continental", None, "agua"),
        ("Influencia urbana", "Influencia urbana", "urbano"),
        ("Florestamento/Reflorestamento com Pinus", "Florestamento/Reflorestamento com Pinus", "silvicultura"),
        ("Estepe Gramineo-Lenhosa", None, "campo_nativo"),
        ("Formacao Pioneira com influencia fluvial e/ou lacustre", None, "banhado"),
        ("Floresta Estacional Decidual Montana", None, "floresta_nativa"),
        ("Vegetacao Secundaria", "Vegetacao Secundaria sem palmeiras", "vegetacao_secundaria"),
    ],
)
def test_classes_do_mapa_real(legenda, uso, esperado):
    assert h.classe_cobertura(legenda, uso) == esperado


# ---------------------------------------------------------------------------
# Solo -> grupo hidrologico
# ---------------------------------------------------------------------------
def test_latossolo_argiloso_e_grupo_a():
    """A inversao que a tabela americana induz, e que erraria o planalto."""
    assert h.grupo_hidrologico("LATOSSOLO", "LATOSSOLO VERMELHO", "muito argilosa") == "A"


def test_neossolo_litolico_e_d_mesmo_arenoso():
    """Solo raso nao tem para onde infiltrar — a profundidade manda na textura."""
    assert h.grupo_hidrologico("NEOSSOLO", "NEOSSOLO LITOLICO", "media cascalhenta") == "D"
    assert h.grupo_hidrologico("NEOSSOLO", "NEOSSOLO QUARTZARENICO", "arenosa") == "A"


def test_hidromorfico_e_planossolo_sao_d():
    assert h.grupo_hidrologico("GLEISSOLO", "GLEISSOLO HAPLICO", "argilosa") == "D"
    assert h.grupo_hidrologico("PLANOSSOLO", "PLANOSSOLO HAPLICO", "arenosa/media") == "D"


def test_agua_e_area_urbana_nao_tem_grupo():
    """None e resposta legitima: preencher com 'C' inventaria terreno."""
    assert h.grupo_hidrologico(None, "CORPO D'AGUA CONTINENTAL", None) is None
    assert h.grupo_hidrologico(None, "AREA URBANA", None) is None


# ---------------------------------------------------------------------------
# Balanco
# ---------------------------------------------------------------------------
def test_cn_cresce_de_a_para_d():
    """Se esta ordem quebrar, a tabela foi editada errada — e nada mais vale."""
    for cobertura in ("agricultura", "pastagem", "floresta_nativa", "campo_nativo"):
        cns = [h.cn_de(g, cobertura) for g in "ABCD"]
        assert cns == sorted(cns), cobertura
        assert cns[0] < cns[-1], cobertura


def test_chuva_abaixo_da_perda_inicial_nao_escoa():
    """Ia = 0,2S: abaixo disso a chuva molha o terreno e para."""
    cn = 70.0
    s = 25400 / cn - 254
    assert h.escoamento_mm(0.2 * s - 1, cn) == 0.0
    assert h.escoamento_mm(0.2 * s + 20, cn) > 0.0


def test_escoamento_nunca_excede_a_chuva():
    for cn in (40.0, 70.0, 98.0):
        for p in (5.0, 50.0, 200.0, 400.0):
            assert 0.0 <= h.escoamento_mm(p, cn) <= p


def test_solo_umido_escoa_mais():
    """AMC III nao e refinamento: o desastre acontece na terceira chuva."""
    cn2 = 74.0
    cn3 = h.cn_umidade_alta(cn2)
    assert cn3 > cn2
    assert h.escoamento_mm(100.0, cn3) > h.escoamento_mm(100.0, cn2)


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def resultado():
    return h.build()


def test_cobre_o_estado(resultado):
    assert len(resultado.rows) >= 490
    assert all(30 <= r["cn2"] <= 100 for r in resultado.rows)


def test_declara_os_proprios_limites(resultado):
    """Camada quase toda modelada sem limite declarado e o pior caso possivel."""
    assert len(resultado.limites) >= 5
    junto = " ".join(resultado.limites).lower()
    for termo in ("vazao", "1:250.000", "agropecuaria", "calibrado"):
        assert termo in junto, termo


def test_parametro_de_perda_inicial_viaja_no_payload(resultado):
    """Trocar 0,2S por 0,05S precisa ser visivel de fora, nao um commit."""
    assert resultado.resumo["razao_ia"] == h.RAZAO_IA


def test_planalto_infiltra_mais_que_encosta_de_basalto_raso(resultado):
    """Prova de sanidade contra o mapa, nao contra o codigo.

    Muitos Capoes esta sobre Latossolo profundo do Planalto dos Campos Gerais;
    Nova Brescia esta sobre Neossolo Litolico do Vale do Taquari — a encosta
    que a cheia de 2023 levou. Se o modelo nao separar esses dois, ele nao
    esta descrevendo o estado.
    """
    por_nome = {r["municipio"]: r for r in resultado.rows}
    assert por_nome["Muitos Capões"]["cn2"] < por_nome["Nova Bréscia"]["cn2"] - 10


def test_chuva_de_projeto_e_plausivel_para_o_rs():
    """Guarda contra o ano de cobertura parcial entrando como maximo anual.

    O maximo de um ano com 60 dias observados nao e o maximo daquele ano — e
    o maior de uma amostra pequena, sistematicamente menor. Misturado aos anos
    completos, ele puxa Gumbel inteiro para baixo, e o efeito e pior nas
    estacoes urbanas recentes: Porto Alegre saia com chuva de TR 2 de 32 mm,
    um terco do plausivel, sem erro nenhum no caminho.

    A faixa abaixo e larga e vem da ordem de grandeza conhecida de chuva
    diaria no estado — nao e calibragem, e deteccao de absurdo.
    """
    chuvas = h.chuvas_de_projeto()
    assert len(chuvas) >= 40
    p2 = [c.por_tr[2] for c in chuvas.values()]
    p100 = [c.por_tr[100] for c in chuvas.values()]
    assert 60 <= min(p2), f"TR2 baixo demais: {min(p2)} mm"
    assert max(p2) <= 160
    assert 110 <= min(p100)
    assert max(p100) <= 400
    for c in chuvas.values():
        anteriores = [c.por_tr[tr] for tr in h.TR_ANOS]
        assert anteriores == sorted(anteriores), c.estacao


def test_regioes_agregam_por_unidade_de_relevo(resultado):
    """Bacia nao respeita divisa; a unidade geomorfologica e o mais proximo disso."""
    assert resultado.regioes
    for r in resultado.regioes:
        assert r["n_municipios"] >= 1
        assert r["cn2_medio"] is None or 30 <= r["cn2_medio"] <= 100
