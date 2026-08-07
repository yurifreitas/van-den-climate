"""Front — instrumento de auditoria, nao dashboard de previsao (§9.1).

Existe para tornar visivel a distancia entre o que foi MEDIDO e o que e PRIOR.
Todo painel declara de que lado da fronteira o numero veio — inclusive se o
lado e "sintetico", via o selo visivel definido em `_synthetic_badge`.

Fase 1-2 (ADR-011): Streamlit sobre Parquet. React so a partir da Fase 7.
    streamlit run app/main.py
"""
from __future__ import annotations

import streamlit as st

from app import charts, data_source as ds, fixtures
from app.theme import BRUMA, CSS, GIZ

st.set_page_config(page_title="Engine Climatica RS", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


def _empty(msg: str, action: str) -> None:
    """Estado vazio e convite a acao, nao decoracao (§9.2)."""
    st.markdown(
        f"<div class='panel'><b>{msg}</b><br>"
        f"<span class='muted'>{action}</span></div>",
        unsafe_allow_html=True,
    )


def _synthetic_badge(resolved_list: list[ds.Resolved]) -> None:
    """Selo "DADO SINTETICO" — regra inegociavel do brief.

    Aparece assim que QUALQUER fonte usada pela visao ainda vem de fixtures.
    Some sozinho, sem interacao do usuario, no primeiro reload apos o parquet
    real aparecer em disco (a deteccao vive em `app/data_source.py`).
    """
    # Regra dura: FRIO/QUENTE sao exclusivos do dado (theme.py). O selo e
    # interface, nao dado — por isso usa apenas GIZ/BRUMA, diferenciado por
    # peso de borda tracejada (sintetico) vs solida (medido), nunca por cor
    # de anomalia. `test_palette_rule` verifica isto por inspecao de texto.
    if any(r.is_synthetic for r in resolved_list):
        st.markdown(
            f"<div style='display:inline-block;padding:.2rem .6rem;border:1px dashed {GIZ};"
            f"border-radius:2px;color:{GIZ};font-family:\"IBM Plex Mono\",monospace;"
            f"font-size:.75rem;letter-spacing:.05em;margin-bottom:.6rem'>"
            "DADO SINTETICO — fixtures deterministicas, nao e medicao real"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<div style='display:inline-block;padding:.2rem .6rem;border:1px solid {BRUMA};"
            f"border-radius:2px;color:{BRUMA};font-family:\"IBM Plex Mono\",monospace;"
            f"font-size:.75rem;letter-spacing:.05em;margin-bottom:.6rem'>"
            "DADO MEDIDO — lido de data/interim ou data/features"
            "</div>",
            unsafe_allow_html=True,
        )


VIEWS = ["Estado", "Previsao", "Evidencia", "Ledger", "Saude dos dados"]
view = st.sidebar.radio("Visao", VIEWS)
st.sidebar.markdown(
    "<span class='muted'>Ancora 1951-1990 · avaliacao 1991-2026 · n=36<br>"
    "Regra de features congelada em 2026-08-07<br><br>"
    "<b>Mapa das visoes</b><br>"
    "Estado — o que o presente parece, comparado ao clima<br>"
    "Previsao — o que a engine emite para OND, vs climatologia<br>"
    "Evidencia — de onde vem o numero (atribuicao por bloco)<br>"
    "Ledger — a engine ja acertou antes?<br>"
    "Saude dos dados — o dado aguenta a pergunta?</span>",
    unsafe_allow_html=True,
)

st.title("Engine Climatica RS")

# ---------------------------------------------------------------------------
if view == "Estado":
    st.subheader("Regua de surpresa — o presente e raro ou comum, por variavel?")
    st.markdown(
        "<span class='muted'>Percentil causal (resolucao 1/t) de cada bloco de "
        "features (§feature_blocks.yaml) contra a propria historia ate o instante "
        "de emissao. Escala unica FRIO->QUENTE em todos os canais: comparavel de "
        "um golpe de vista, sem reler eixo.</span>", unsafe_allow_html=True,
    )
    state = ds.resolve_surprise_state()
    _synthetic_badge([state])
    st.plotly_chart(charts.surprise_ruler(state.df), use_container_width=True)

    st.markdown("---")
    st.subheader("ONI e SAM — fase da anomalia, nao so nivel")
    oni, sam = ds.resolve_oni(), ds.resolve_sam()
    _synthetic_badge([oni, sam])
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(charts.diverging_timeseries(oni.df.tail(180), label="ONI"),
                         use_container_width=True)
    with c2:
        st.plotly_chart(charts.diverging_timeseries(sam.df.tail(180), label="SAM"),
                         use_container_width=True)

# ---------------------------------------------------------------------------
elif view == "Previsao":
    st.subheader("Trio de alvos OND — distribuicao, sempre ao lado da climatologia")
    st.markdown(
        "<span class='muted'>Frequencia de dias umidos · intensidade media em dia "
        "umido · p95 diario. Nunca um numero sozinho — sempre com a climatologia "
        "1951-1990 ao lado e a barra de erro da previsao.</span>",
        unsafe_allow_html=True,
    )
    fc = ds.resolve_target_forecast()
    _synthetic_badge([fc])
    if fc.is_synthetic:
        st.markdown(
            "<div class='panel'><b>Nenhum modelo aceito sob a ADR-007.</b><br>"
            "<span class='muted'>Ate que o limite inferior do IC 90% de RPSS seja "
            "&gt; 0, a climatologia permanece como previsao vigente — os graficos "
            "abaixo mostram exatamente isso (previsao ≈ climatologia, ruido de "
            "amostra), com dado sintetico ate a Fase 6 rodar.</span></div>",
            unsafe_allow_html=True,
        )
    cols = st.columns(3)
    for col, (_, row) in zip(cols, fc.df.iterrows()):
        with col:
            st.plotly_chart(charts.tercile_diagram(row), use_container_width=True)

# ---------------------------------------------------------------------------
elif view == "Evidencia":
    st.subheader("Atribuicao por bloco — de onde vem o numero")
    st.markdown(
        "<span class='muted'>Quanto vem de Estado ENSO, Dinamica ENSO, SAM, "
        "Atlantico Sul e Tendencia — inclusive o contrafactual 'removendo ENSO', "
        "para separar sinal ENSO de tendencia de fundo (§bloco `trend`).</span>",
        unsafe_allow_html=True,
    )
    attr = ds.resolve_block_attribution()
    _synthetic_badge([attr])
    st.plotly_chart(charts.block_attribution_bars(attr.df), use_container_width=True)
    if attr.is_synthetic:
        _empty("Camada 5 (analogos, M-SSA, HMM) nao construida.",
               "A atribuicao acima e ilustrativa — hierarquia plausivel, nao medida.")

# ---------------------------------------------------------------------------
elif view == "Ledger":
    st.subheader("Previsoes emitidas — append-only, imutavel")
    st.markdown(
        "<span class='muted'>Unica defesa contra reavaliacao retrospectiva. Sem "
        "isto, ninguem sabe se a engine funciona.</span>", unsafe_allow_html=True,
    )
    ledger = ds.resolve_ledger()
    _synthetic_badge([ledger])
    target = st.selectbox("Alvo", fixtures.TARGET_IDS,
                           format_func=lambda t: fixtures.TARGET_LABELS[t])
    st.plotly_chart(charts.ledger_timeline(ledger.df, target_id=target), use_container_width=True)
    with st.expander("Tabela bruta"):
        st.dataframe(ledger.df, use_container_width=True)

# ---------------------------------------------------------------------------
else:
    st.subheader("Saude dos dados — Camada 2 exposta, nao escondida")
    st.markdown(
        "<span class='muted'>O dado aguenta a pergunta? Cobertura por estacao e "
        "ano, e a transicao convencional->automatica do INMET, que quebra "
        "homogeneidade e precisa ser visivel, nao suavizada.</span>",
        unsafe_allow_html=True,
    )
    quality = ds.resolve_quality()
    _synthetic_badge([quality])
    st.plotly_chart(
        charts.coverage_heatmap(quality.df, fixtures.STATIONS if quality.is_synthetic else None),
        use_container_width=True,
    )

    st.markdown("---")
    st.subheader("Diagrama de confiabilidade — a climatologia esta calibrada?")
    rel = ds.resolve_reliability()
    _synthetic_badge([rel])
    st.plotly_chart(charts.reliability_diagram(rel.df), use_container_width=True)
