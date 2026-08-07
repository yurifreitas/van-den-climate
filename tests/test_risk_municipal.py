"""Testes do indice de risco municipal (src/risk/municipal.py).

O teste central deste arquivo e `test_ausencia_de_dado_nunca_vira_risco_alto`.
Ele existe porque a primeira versao do modelo colocou Bage em 1o lugar entre
os 497 municipios com 90 de 100 pontos — nao por risco, mas porque o
municipio nao respondeu ao suplemento do MUNIC 2024. Sobrou so exposicao
(peso 0.28), a renormalizacao sobre componentes presentes esticou esse unico
componente para a escala inteira, e a lacuna virou a manchete.

Numa lista de prioridade preventiva esse erro e pior que subestimar risco:
desloca orcamento para onde nao ha evidencia, e o faz com aparencia de
certeza. Como e uma falha silenciosa — o numero sai bonito e ordenado —, ela
so nao volta se estiver travada por teste.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.risk import municipal as m


def _linha(**over) -> pd.Series:
    """Municipio-base: atingido, com plano executado, sem lacuna e sem dano."""
    base = {
        "cod_mun": 4300000,
        "municipio": "Teste",
        "populacao": 10_000,
        "atingido": True,
        "alerta_emitido": True,
        "alerta_sms": True,
        "alerta_app": True,
        "alerta_sirene": False,
        "alerta_alcance": "Menos de 100 a 90%",
        "plano_contingencia": True,
        "plano_executado": True,
    }
    for col in (*m.PERIGOS_HIDRICOS, *m.DANOS, *m.DEFICIT_MOTIVOS, *m.GRUPOS_VULNERAVEIS):
        base.setdefault(col, False)
    base.update(over)
    return pd.Series(base)


# ---------------------------------------------------------------------------
# A regressao que originou o modulo de cobertura minima
# ---------------------------------------------------------------------------
def test_ausencia_de_dado_nunca_vira_risco_alto():
    """So exposicao presente (peso 0.28 < 0.60) => sem indice, nao indice alto."""
    impacto = m.Componente(None, None, {})
    deficit = m.Componente(None, None, {})
    exposicao = m.Componente(0.99, "measured", {})

    disponiveis = {k: v.valor for k, v in
                   {"impacto": impacto, "deficit": deficit, "exposicao": exposicao}.items()
                   if v.valor is not None}
    peso = sum(m.PESOS[k] for k in disponiveis)
    tem_sinal = ("impacto" in disponiveis) or ("deficit" in disponiveis)

    assert peso < m.MIN_COBERTURA_PESO
    assert not tem_sinal


def test_municipio_sem_resposta_fica_fora_do_ranking(tabela):
    """Ninguem com `completude='insuficiente'` tem score, nivel ou basis."""
    insuficientes = [r for r in tabela.rows if r["completude"] == "insuficiente"]
    assert insuficientes, "fixture perdeu o caso de cobertura insuficiente"
    for r in insuficientes:
        assert r["score"] is None
        assert r["level"] is None
        assert r["basis"] is None


def test_ranking_nao_comeca_com_municipio_sem_base(tabela):
    """O topo da lista tem de ser evidencia, nunca lacuna."""
    assert tabela.rows[0]["score"] is not None
    assert tabela.rows[0]["completude"] != "insuficiente"


# ---------------------------------------------------------------------------
# Ausente != zero (DESIGN.md §5)
# ---------------------------------------------------------------------------
def test_nao_atingido_e_zero_medido_e_nao_ausente():
    """Responder 'nao fui atingido' e uma ausencia OBSERVADA: 0.0 medido."""
    comp = m._componente_impacto(_linha(atingido=False))
    assert comp.valor == 0.0
    assert comp.basis == "measured"


def test_nao_respondeu_e_ausente_e_nao_zero():
    comp = m._componente_impacto(_linha(atingido=None))
    assert comp.valor is None
    assert comp.basis is None
    assert "motivo" in comp.detalhe


def test_manutencao_de_ativos_e_lacuna_declarada_em_todos(tabela):
    """A divida estrutural aparece em TODA linha, com motivo e sem valor."""
    for r in tabela.rows:
        ativos = r["componentes"]["manutencao_ativos"]
        assert ativos["valor"] is None
        assert ativos["basis"] is None
        assert ativos["detalhe"]["motivo"]


# ---------------------------------------------------------------------------
# Deficit de prevencao: a pergunta que motivou a camada
# ---------------------------------------------------------------------------
def test_sem_plano_pesa_mais_que_plano_nao_executado():
    sem_plano = m._componente_deficit(_linha(plano_contingencia=False, plano_executado=None))
    nao_exec = m._componente_deficit(_linha(plano_contingencia=True, plano_executado=False))
    assert sem_plano.valor > nao_exec.valor
    assert "sem plano de contingencia" in sem_plano.detalhe["lacunas"]


def test_motivos_declarados_somam_ao_deficit():
    base = m._componente_deficit(_linha(plano_contingencia=True, plano_executado=False))
    com_motivos = m._componente_deficit(
        _linha(
            plano_contingencia=True,
            plano_executado=False,
            falta_recurso_financeiro=True,
            falta_treinamento=True,
        )
    )
    assert com_motivos.valor > base.valor
    assert any("financeiro" in l for l in com_motivos.detalhe["lacunas"])


def test_alcance_baixo_do_alerta_conta_como_deficit():
    alto = m._componente_deficit(_linha(alerta_alcance="Menos de 100 a 90%"))
    baixo = m._componente_deficit(_linha(alerta_alcance="Menos de 5%"))
    assert baixo.valor > alto.valor


def test_deficit_limitado_a_um():
    pior = m._componente_deficit(
        _linha(
            plano_contingencia=False,
            plano_executado=False,
            alerta_emitido=False,
            alerta_alcance="Menos de 5%",
            **{k: True for k in m.DEFICIT_MOTIVOS},
        )
    )
    assert 0.0 <= pior.valor <= 1.0


# ---------------------------------------------------------------------------
# Perigo sazonal: estadual, uniforme, nunca reordena
# ---------------------------------------------------------------------------
def test_perigo_sazonal_nunca_inverte_dois_municipios():
    """H e um multiplicador global e nao pode inverter nenhum par.

    A comparacao e feita so entre pares que o modelo de fato separa (score
    diferente nas duas condicoes). Empate na casa decimal publicada nao e
    reordenacao — e resolucao insuficiente, e o desempate por cod_mun em
    build_table garante que ele ao menos nao produza uma lista instavel.

    Se este teste falhar de verdade, o bug e de escopo: significa que o ONI
    passou a mexer na ORDEM municipal, e ele nao tem resolucao para isso.
    """
    elnino = {r["cod_mun"]: r["score"] for r in m.build_table(2.0).rows if r["score"] is not None}
    lanina = {r["cod_mun"]: r["score"] for r in m.build_table(-1.5).rows if r["score"] is not None}
    codigos = sorted(set(elnino) & set(lanina))

    for i, a in enumerate(codigos):
        for b in codigos[i + 1 :]:
            da = elnino[a] - elnino[b]
            db = lanina[a] - lanina[b]
            if da != 0 and db != 0:
                assert (da > 0) == (db > 0), f"{a} e {b} inverteram entre El Nino e La Nina"


def test_ranking_e_deterministico():
    """Duas construcoes com a mesma entrada devolvem a mesma ordem."""
    a = [r["cod_mun"] for r in m.build_table(1.0).rows]
    b = [r["cod_mun"] for r in m.build_table(1.0).rows]
    assert a == b


def test_perigo_sazonal_desloca_o_nivel_de_todos():
    forte = {r["cod_mun"]: r["score"] for r in m.build_table(2.0).rows if r["score"] is not None}
    fraco = {r["cod_mun"]: r["score"] for r in m.build_table(-1.5).rows if r["score"] is not None}
    assert all(forte[c] > fraco[c] for c in forte)


def test_indice_nunca_zera_fora_da_estacao():
    """Piso de 0.62 no multiplicador: risco estrutural nao some em ONI neutro.

    Um indice que cai a zero fora da estacao ensina o gestor a desligar a
    atencao — o oposto do objetivo de uma camada preventiva.
    """
    neutro = m.build_table(0.0)
    topo = neutro.rows[0]["score"]
    assert topo is not None and topo > 20.0


def test_hazard_sem_oni_e_zero_mas_nao_none():
    valor, rotulo = m.hazard_sazonal(None)
    assert valor == 0.0
    assert rotulo == "indisponivel"


# ---------------------------------------------------------------------------
# Contrato de saida
# ---------------------------------------------------------------------------
def test_cobre_os_497_municipios(tabela):
    assert len(tabela.rows) == 497
    assert len({r["cod_mun"] for r in tabela.rows}) == 497


def test_score_dentro_da_escala(tabela):
    for r in tabela.rows:
        if r["score"] is not None:
            assert 0.0 <= r["score"] <= 100.0


def test_todo_componente_com_valor_tem_basis(tabela):
    """Numero sem selo e bug de interface (contrato §0), inclusive por componente."""
    for r in tabela.rows:
        for nome, comp in r["componentes"].items():
            if comp["valor"] is not None:
                assert comp["basis"] is not None, f"{r['municipio']}/{nome}: valor sem basis"


def test_model_card_publica_pesos_cortes_e_limites():
    card = m.model_card()
    assert card["pesos"] == m.PESOS
    assert set(card["cortes"]) == {"high", "elevated", "moderate"}
    assert len(card["limites"]) >= 5
    assert any("nao e previsao" in l.lower() for l in card["limites"])


# ---------------------------------------------------------------------------
# Cenarios de horizonte — o que da para dizer sobre 2026 e sobre 2027
# ---------------------------------------------------------------------------
def test_cenario_desconhecido_falha_alto():
    with pytest.raises(ValueError, match="cenario desconhecido"):
        m.build_table(1.39, "chute2030")


def test_estrutural_declara_perigo_sazonal_ausente_e_nao_zero(tabela_estrutural):
    """Para 2027 nao ha previsao ENSO. Ausente e ausente, nunca 'neutro'.

    Marcar H como 0.0 diria "prevemos ENSO neutro em 2027", que e uma
    afirmacao — e uma que ninguem consegue sustentar a 14 meses.
    """
    for r in tabela_estrutural.rows:
        h = r["componentes"]["perigo_sazonal"]
        assert h["valor"] is None
        assert h["basis"] is None
        assert h["detalhe"]["motivo"]


def test_estrutural_nao_aplica_desconto_sazonal(tabela_estrutural):
    assert tabela_estrutural.cenario_spec["multiplicador"] == 1.0


def test_ond2026_ancora_no_limiar_do_proprio_boletim():
    """A ancora e 'muito forte' (ONI >= 2.0), categoria do CPC — nao um chute."""
    t = m.build_table(1.39, "ond2026")
    assert m.CENARIOS["ond2026"]["oni_ancora"] == 2.0
    assert t.rows[0]["componentes"]["perigo_sazonal"]["detalhe"]["oni"] == 2.0
    assert t.rows[0]["componentes"]["perigo_sazonal"]["basis"] == "modeled"


def test_cenario_nunca_inverte_dois_municipios():
    """Trocar de horizonte reescala, nunca reordena — mesma regra de escopo."""
    tabelas = {c: {r["cod_mun"]: r["score"] for r in m.build_table(1.39, c).rows
                   if r["score"] is not None}
               for c in ("atual", "ond2026", "estrutural")}
    a, b = tabelas["atual"], tabelas["estrutural"]
    codigos = sorted(set(a) & set(b))
    for i, x in enumerate(codigos):
        for y in codigos[i + 1:]:
            da, db = a[x] - a[y], b[x] - b[y]
            if da != 0 and db != 0:
                assert (da > 0) == (db > 0), f"{x} e {y} inverteram entre cenarios"


def test_saturacao_e_declarada_quando_multiplicador_bate_no_teto():
    """Dois cenarios com numeros identicos precisam vir com a explicacao.

    Sem `leitura_saturacao` a coincidencia numerica entre 'OND 2026' e
    'estrutural' parece bug de software em vez do que e: o outlook e forte o
    bastante para nao aplicar nenhum desconto.
    """
    t = m.build_table(1.39, "ond2026")
    assert t.cenario_spec["saturado"] is True
    assert t.cenario_spec["leitura_saturacao"]


def test_model_card_declara_a_ausencia_de_previsao_para_2027():
    card = m.model_card()
    h = card["horizonte_previsao"]
    assert h["limite_util_meses"] <= 12
    assert "2027" in h["consequencia"]
    assert any("2027" in l for l in card["limites"])
    assert any("nao desta engine" in l.lower() or "nao e desta engine" in l.lower()
               for l in card["limites"])


@pytest.fixture(scope="module")
def tabela_estrutural():
    if not m.MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida — rode `python -m src.ingest.ibge_rs`")
    return m.build_table(1.39, "estrutural")


@pytest.fixture(scope="module")
def tabela():
    if not m.MUNIC_PARQUET.exists():
        pytest.skip("base municipal nao ingerida — rode `python -m src.ingest.ibge_rs`")
    return m.build_table(1.39)
