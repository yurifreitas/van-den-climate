"""Front — instrumento de auditoria, nao dashboard de previsao (§9.1).

Existe para tornar visivel a distancia entre o que foi MEDIDO e o que e PRIOR.
Todo painel declara de que lado da fronteira o numero veio.

Fase 1-2 (ADR-011): Streamlit sobre Parquet. React so a partir da Fase 7.
    streamlit run app/main.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from app.theme import BRUMA, CSS, GIZ, diverging

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "features"
LEDGER = ROOT / "ledger" / "forecasts.parquet"

st.set_page_config(page_title="Engine Climatica RS", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)


def _empty(msg: str, action: str) -> None:
    """Estado vazio e convite a acao, nao decoracao (§9.2)."""
    st.markdown(
        f"<div class='panel'><b>{msg}</b><br>"
        f"<span class='muted'>{action}</span></div>",
        unsafe_allow_html=True,
    )


def surprise_ruler(df: pd.DataFrame) -> None:
    """Signature (§9.2) — faixa vertical por variavel, estilo console de mixagem.

    Cada canal: percentil causal atual + trilha de persistencia de 12 meses.
    Todas as variaveis na MESMA escala, legiveis num golpe de vista. E a
    traducao visual do principio de linguagem comum de anomalia.
    """
    cols = st.columns(len(df))
    for col, (_, row) in zip(cols, df.iterrows()):
        pct = float(row["percentile"])
        trail = row.get("trail_12m") or []
        bars = "".join(
            f"<div style='height:3px;margin:1px 0;background:{diverging(t)}'></div>"
            for t in trail
        )
        col.markdown(
            f"<div class='panel' style='text-align:center'>"
            f"<div class='muted'>{row['label']}</div>"
            f"<div style='height:120px;display:flex;flex-direction:column-reverse;"
            f"justify-content:flex-start'>{bars}</div>"
            f"<div style='height:10px;background:{diverging(pct)};"
            f"border:1px solid {GIZ}'></div>"
            f"<div class='mono' style='font-size:1.1rem'>{pct:.2f}</div>"
            f"<div class='muted'>{row.get('anchor_mode','—')}</div></div>",
            unsafe_allow_html=True,
        )


VIEWS = ["Estado", "Previsao", "Evidencia", "Ledger", "Saude dos dados"]
view = st.sidebar.radio("Visao", VIEWS)
st.sidebar.markdown(
    f"<span class='muted'>Ancora 1951–1990 · avaliacao 1991–2026 · n=36<br>"
    f"Regra de features congelada em 2026-08-07</span>",
    unsafe_allow_html=True,
)

st.title("Engine Climatica RS")

if view == "Estado":
    st.subheader("Regua de surpresa — percentil historico por variavel")
    path = FEATURES / "state.parquet"
    if path.exists():
        surprise_ruler(pd.read_parquet(path))
    else:
        _empty("Nenhum estado calculado ainda.",
               "Execute a Fase 1 (ingestao) e a Fase 4 (representacao causal).")

elif view == "Previsao":
    st.subheader("Trio de alvos OND — distribuicao, sempre ao lado da climatologia")
    st.markdown("<span class='muted'>Frequencia de dias umidos · intensidade "
                "media em dia umido · p95 diario. Nunca um numero sozinho.</span>",
                unsafe_allow_html=True)
    _empty("Nenhum modelo aceito sob a ADR-007.",
           "Ate que o limite inferior do IC 90% de RPSS seja > 0, a climatologia "
           "permanece como previsao vigente. Isto e o comportamento correto.")

elif view == "Evidencia":
    st.subheader("Analogos historicos e atribuicao por bloco")
    st.markdown("<span class='muted'>Quanto vem de ENSO, SAM, Atlantico Sul e "
                "tendencia — inclusive o contrafactual 'removendo ENSO'.</span>",
                unsafe_allow_html=True)
    _empty("Camada 5 nao construida.", "Fase 5: analogos com kernel, M-SSA, HMM.")

elif view == "Ledger":
    st.subheader("Previsoes emitidas — append-only, imutavel")
    st.markdown("<span class='muted'>Unica defesa contra reavaliacao "
                "retrospectiva. Sem isto, ninguem sabe se a engine funciona.</span>",
                unsafe_allow_html=True)
    if LEDGER.exists():
        st.dataframe(pd.read_parquet(LEDGER), use_container_width=True)
    else:
        _empty("Nenhuma previsao emitida.", "Fase 8.")

else:
    st.subheader("Saude dos dados — Camada 2 exposta, nao escondida")
    path = FEATURES / "quality.parquet"
    if path.exists():
        st.dataframe(pd.read_parquet(path), use_container_width=True)
    else:
        _empty("Mascara de confiabilidade nao gerada.",
               "Fase 2: homogeneizacao e deteccao de quebras "
               "(atencao a transicao convencional->automatica do INMET).")
