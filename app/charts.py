"""Graficos Plotly do instrumento de auditoria (§9.2).

Toda figura aqui usa o template escuro definido em `_apply_layout` e a
paleta de `app/theme.py`. Regra dura, repetida em cada funcao: FRIO/QUENTE
(anomalia negativa/positiva) so aparecem tocando o DADO — barras de eixo,
grade, titulo, anotacao de contexto usam sempre GIZ/BRUMA/CARTA. Isso e
verificado em `tests/test_app.py::test_palette_rule`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.theme import ABISSAL, BRUMA, CARTA, FONT_BODY, FONT_MONO, FRIO, GIZ, QUENTE

_GRID = "#253036"  # mesma linha de borda de `.panel` no CSS — grade discreta, nao decorativa


def _alpha(hex_color: str, alpha: float) -> str:
    """Hex -> rgba() com transparencia. Plotly nao aceita hex de 8 digitos
    (#RRGGBBAA) em `fillcolor`, entao a banda divergente precisa disto."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _apply_layout(fig: go.Figure, *, title: str | None = None, height: int = 360) -> go.Figure:
    """Aplica o tema escuro comum a todas as figuras (fundo, fonte, grade).

    Centralizado aqui para que uma mudanca de paleta nunca precise ser
    repetida grafico a grafico — e o mesmo motivo pelo qual theme.py existe.
    """
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=ABISSAL,
        plot_bgcolor=CARTA,
        font=dict(family=FONT_BODY, color=GIZ, size=13),
        title=dict(text=title, font=dict(family=FONT_MONO, size=14, color=GIZ)) if title else None,
        margin=dict(l=48, r=24, t=48 if title else 16, b=40),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=BRUMA, size=11)),
        hoverlabel=dict(bgcolor=CARTA, font=dict(family=FONT_MONO, color=GIZ)),
    )
    fig.update_xaxes(gridcolor=_GRID, zerolinecolor=_GRID, tickfont=dict(family=FONT_MONO, color=BRUMA))
    fig.update_yaxes(gridcolor=_GRID, zerolinecolor=_GRID, tickfont=dict(family=FONT_MONO, color=BRUMA))
    return fig


# ---------------------------------------------------------------------------
# 1. Regua de Surpresa — elemento-assinatura (§9.2)
# ---------------------------------------------------------------------------

def surprise_ruler(state_df: pd.DataFrame) -> go.Figure:
    """Console de mixagem: um canal vertical por variavel, mesma escala 0-1.

    Cada canal e uma coluna de calor (heatmap 1-larga) mostrando a trilha dos
    ultimos 12 meses empilhada de baixo para cima, com o mes mais recente no
    topo marcado por um traco solido — o "fader" do console. A escala
    divergente e identica entre canais de proposito: o ponto do grafico e
    permitir comparar ENSO, SAM e Atlantico Sul num so golpe de vista, sem
    reler eixo.
    """
    labels = state_df["label"].tolist()
    n = len(labels)
    fig = go.Figure()

    z = []
    for _, row in state_df.iterrows():
        trail = list(row.get("trail_12m") or [])
        if not trail:
            trail = [row["percentile"]]
        # normaliza para exatamente 12 pontos (preenche com o mais antigo disponivel)
        if len(trail) < 12:
            trail = [trail[0]] * (12 - len(trail)) + trail
        z.append(trail[-12:])
    z = np.array(z)  # shape (n_var, 12), cada linha = trilha temporal

    fig.add_trace(go.Heatmap(
        z=z,
        x=list(range(-11, 1)),
        y=labels,
        colorscale=[[0.0, FRIO], [0.5, CARTA], [1.0, QUENTE]],
        zmin=0, zmax=1,
        zmid=0.5,
        showscale=True,
        colorbar=dict(
            title=dict(text="percentil", font=dict(color=BRUMA, size=10)),
            tickfont=dict(family=FONT_MONO, color=BRUMA, size=10),
            thickness=12,
        ),
        hovertemplate="%{y}<br>t%{x} meses · percentil=%{z:.2f}<extra></extra>",
        xgap=2, ygap=6,
    ))
    fig.update_xaxes(title="meses ate o presente (t=0)", dtick=1)
    fig.update_yaxes(autorange="reversed")
    return _apply_layout(fig, title="REGUA DE SURPRESA — percentil causal, trilha de 12 meses", height=120 + 40 * n)


# ---------------------------------------------------------------------------
# 2. Serie temporal com banda divergente (ONI, SAM)
# ---------------------------------------------------------------------------

def diverging_timeseries(df: pd.DataFrame, *, label: str, zero_line_label: str = "ancora") -> go.Figure:
    """Anomalia ao longo do tempo, preenchimento FRIO abaixo de zero / QUENTE
    acima. E o padrao "carta sinotica" pedido: le-se a fase, nao so o nivel.
    """
    x = df["timestamp"]
    y = df["value"].to_numpy()
    pos = np.where(y >= 0, y, 0.0)
    neg = np.where(y < 0, y, 0.0)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=pos, mode="none", fill="tozeroy", fillcolor=_alpha(QUENTE, 0.33),
        name="anomalia positiva", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=neg, mode="none", fill="tozeroy", fillcolor=_alpha(FRIO, 0.33),
        name="anomalia negativa", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="lines", line=dict(color=GIZ, width=1),
        name=label, hovertemplate="%{x|%Y-%m}<br>%{y:.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=BRUMA, width=1, dash="dot"), annotation_text=zero_line_label,
                   annotation_font=dict(color=BRUMA, size=10))
    return _apply_layout(fig, title=f"{label} — anomalia mensal", height=280)


# ---------------------------------------------------------------------------
# 3. Diagrama de tercis — trio de alvos, previsao vs climatologia
# ---------------------------------------------------------------------------

def tercile_diagram(target_row: pd.Series) -> go.Figure:
    """Barras pareadas climatologia vs previsao por tercil, com IC na previsao.

    Nunca mostra a previsao sozinha (regra do brief): a climatologia sempre
    aparece ao lado, na mesma escala, e a barra da previsao carrega a barra
    de erro derivada de `forecast_se`.
    """
    tercis = ["Abaixo", "Perto da norma", "Acima"]
    clim = target_row["climatology"]
    fc = target_row["forecast"]
    se = target_row.get("forecast_se", 0.0)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=tercis, y=clim, name="climatologia (1951-1990)",
        marker=dict(color=CARTA, line=dict(color=BRUMA, width=1)),
        hovertemplate="%{x}<br>climatologia=%{y:.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=tercis, y=fc, name="previsao vigente",
        marker=dict(color=BRUMA),
        error_y=dict(type="data", array=[se] * 3, color=GIZ, thickness=1.5),
        hovertemplate="%{x}<br>previsao=%{y:.2f} ± %{error_y.array:.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="probabilidade", range=[0, max(0.6, max(fc) + se + 0.05)])
    return _apply_layout(fig, title=f"{target_row['target_label']} — tercis", height=300)


# ---------------------------------------------------------------------------
# 4. Atribuicao por bloco, com contrafactual "removendo ENSO"
# ---------------------------------------------------------------------------

def block_attribution_bars(attr_df: pd.DataFrame) -> go.Figure:
    """Barras horizontais de participacao por bloco (§feature_blocks.yaml),
    com uma segunda serie mostrando o mesmo grafico sem os dois blocos ENSO —
    o contrafactual pedido explicitamente no brief.
    """
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=attr_df["label"], x=attr_df["share_full"], orientation="h",
        name="atribuicao (todos os blocos)",
        marker=dict(color=BRUMA),
        hovertemplate="%{y}: %{x:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=attr_df["label"], x=attr_df["share_without_enso"], orientation="h",
        name="contrafactual — removendo ENSO",
        marker=dict(color=CARTA, line=dict(color=GIZ, width=1)),
        hovertemplate="%{y}: %{x:.1%}<extra></extra>",
    ))
    fig.update_layout(barmode="group")
    fig.update_xaxes(title="participacao na variancia explicada", tickformat=".0%")
    return _apply_layout(fig, title="ATRIBUICAO POR BLOCO", height=320)


# ---------------------------------------------------------------------------
# 5. Ledger — previsoes emitidas x observado ao longo do tempo
# ---------------------------------------------------------------------------

def ledger_timeline(ledger_df: pd.DataFrame, *, target_id: str | None = None) -> go.Figure:
    """Cada previsao emitida (OND/ano) como um marcador de tercil previsto,
    com o observado sobreposto — permite ver visualmente se a distribuicao
    prevista bateu o observado, ano a ano, sem resumir num score unico.
    """
    df = ledger_df if target_id is None else ledger_df[ledger_df["target_id"] == target_id]
    df = df.sort_values("issued_at")
    tercile_names = {0: "Abaixo", 1: "Perto", 2: "Acima"}

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["issued_at"], y=df["predicted_tercile"].map(tercile_names),
        mode="markers", name="previsto (climatologia vigente)",
        marker=dict(size=9, color=BRUMA, symbol="diamond"),
        hovertemplate="%{x|%Y}<br>previsto=%{y}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["issued_at"], y=df["observed_tercile"].map(tercile_names),
        mode="markers", name="observado",
        marker=dict(size=9, color=GIZ, symbol="circle-open", line=dict(width=2)),
        hovertemplate="%{x|%Y}<br>observado=%{y}<extra></extra>",
    ))
    fig.update_yaxes(categoryorder="array", categoryarray=["Abaixo", "Perto", "Acima"])
    return _apply_layout(fig, title="LEDGER — previsto vs observado (append-only)", height=320)


# ---------------------------------------------------------------------------
# 6. Mapa de calor de cobertura estacao x ano (saude dos dados)
# ---------------------------------------------------------------------------

def coverage_heatmap(station_df: pd.DataFrame, station_meta: list[dict] | None = None) -> go.Figure:
    """Fracao de dias validos (quality_flag != INVALID) por estacao x ano.

    Mostra lacunas (celulas escuras/vazias) e permite localizar a quebra
    convencional->automatica do INMET via a linha vertical de anotacao por
    estacao (quando `station_meta` traz `automatic_from`).
    """
    df = station_df.copy()
    df["year"] = pd.to_datetime(df["timestamp"]).dt.year
    df["valid"] = df["quality_flag"] != 3  # QualityFlag.INVALID
    cov = df.groupby(["signal_id", "year"])["valid"].mean().reset_index()
    pivot = cov.pivot(index="signal_id", columns="year", values="valid")

    labels = pivot.index.tolist()
    if station_meta:
        id_to_label = {f"prcp_{m['id']}": m["label"] for m in station_meta}
        labels = [id_to_label.get(s, s) for s in pivot.index]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=labels,
        colorscale=[[0.0, ABISSAL], [0.5, "#3A4750"], [1.0, GIZ]],
        zmin=0, zmax=1,
        colorbar=dict(title=dict(text="cobertura", font=dict(color=BRUMA, size=10)),
                       tickfont=dict(family=FONT_MONO, color=BRUMA, size=10)),
        hovertemplate="%{y} · %{x}<br>cobertura=%{z:.0%}<extra></extra>",
    ))
    fig.update_xaxes(title="ano")
    return _apply_layout(fig, title="COBERTURA — estacao x ano", height=120 + 30 * len(labels))


# ---------------------------------------------------------------------------
# 7. Diagrama de confiabilidade (calibracao)
# ---------------------------------------------------------------------------

def reliability_diagram(rel_df: pd.DataFrame) -> go.Figure:
    """Probabilidade prevista vs frequencia observada, com a diagonal de
    calibracao perfeita. Tamanho da bolha = n de observacoes no bin — com
    n_eval=36 (README), nenhum bin tem massa grande, e isso deve ser visivel,
    nao escondido atras de um marcador uniforme.
    """
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode="lines", line=dict(color=BRUMA, dash="dot", width=1),
        name="calibracao perfeita", hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=rel_df["predicted"], y=rel_df["observed"], mode="markers+lines",
        line=dict(color=GIZ, width=1),
        marker=dict(size=rel_df["n"] * 3, color=GIZ, opacity=0.75,
                    line=dict(color=BRUMA, width=1)),
        name="observado por bin",
        hovertemplate="previsto=%{x:.2f}<br>observado=%{y:.2f}<br>n=%{marker.size}<extra></extra>",
        customdata=rel_df["n"],
    ))
    fig.update_xaxes(title="probabilidade prevista", range=[0, 1])
    fig.update_yaxes(title="frequencia observada", range=[0, 1])
    return _apply_layout(fig, title="CONFIABILIDADE (CALIBRACAO)", height=340)
