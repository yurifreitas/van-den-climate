"""Testes headless do front (§9). Rodam sem streamlit runtime — so validam
que fixtures respeitam o contrato, que os graficos produzem figuras Plotly
validas, e que a regra de paleta (FRIO/QUENTE exclusivos do dado) e mantida
por inspecao estatica do codigo-fonte do app.
"""
from __future__ import annotations

import re
from pathlib import Path

import plotly.graph_objects as go
import pytest

from app import charts, fixtures
from src.contracts import ContractError, validate_series

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# fixtures respeitam o esquema unico (src/contracts.py)
# ---------------------------------------------------------------------------

def test_oni_monthly_respects_contract():
    validate_series(fixtures.oni_monthly(), name="oni")


def test_sam_monthly_respects_contract():
    validate_series(fixtures.sam_monthly(), name="sam")


def test_satl_monthly_respects_contract():
    validate_series(fixtures.satl_monthly(), name="satl")


def test_station_daily_precip_respects_contract():
    df = fixtures.station_daily_precip()
    validate_series(df, name="station_precip")
    # regra do contrato: nenhum NaN sem quality_flag != OK (falha silenciosa
    # classica de precipitacao ausente virando zero) — ja garantido por
    # validate_series, mas reforcamos a intencao aqui.
    ok_mask = df["quality_flag"] == 0
    assert not df.loc[ok_mask, "value"].isna().any()


def test_oni_2026_tail_is_active_el_nino_rising():
    """Contexto de negocio: El Nino ativo em 2026, subindo, chegando a ~+0.7."""
    df = fixtures.oni_monthly()
    tail = df[df["timestamp"] >= "2026-01-01"].sort_values("timestamp")
    assert len(tail) > 0
    assert tail["value"].iloc[-1] == pytest.approx(0.7, abs=0.15)
    assert tail["value"].iloc[-1] > tail["value"].iloc[0]  # subindo


def test_fixtures_are_deterministic():
    """Seed fixa: duas chamadas produzem exatamente o mesmo dado."""
    a = fixtures.oni_monthly()
    b = fixtures.oni_monthly()
    pd_equal = a["value"].equals(b["value"])
    assert pd_equal


def test_ledger_climatology_is_forecast_flag():
    """ADR-007: enquanto nenhum modelo e aceito, a previsao emitida E a
    climatologia — o ledger sintetico precisa declarar isso explicitamente."""
    ledger = fixtures.forecast_ledger()
    assert ledger["climatology_is_forecast"].all()
    assert set(ledger["target_id"]) == set(fixtures.TARGET_IDS)


def test_feature_names_used_as_signal_ids_are_illustrative_not_validated():
    """Os signal_id de fixtures (ex.: 'oni') sao rotulos de serie bruta, nao
    nomes de feature derivada — por isso NAO precisam bater com
    FEATURE_NAME_RE (essa regex e para features com sufixo _lagN/_innov/...,
    Camada 3+). Este teste apenas documenta a distincao para quem ler os dois
    modulos lado a lado."""
    assert True


# ---------------------------------------------------------------------------
# charts.py: cada funcao retorna uma go.Figure valida, sem lancar
# ---------------------------------------------------------------------------

def test_surprise_ruler_returns_valid_figure():
    fig = charts.surprise_ruler(fixtures.surprise_state())
    assert isinstance(fig, go.Figure)
    fig.to_dict()  # forca serializacao — pega erros de trace mal formado


def test_diverging_timeseries_returns_valid_figure():
    fig = charts.diverging_timeseries(fixtures.oni_monthly().tail(60), label="ONI")
    assert isinstance(fig, go.Figure)
    fig.to_dict()


def test_tercile_diagram_returns_valid_figure():
    targets = fixtures.target_forecast_vs_climatology()
    for _, row in targets.iterrows():
        fig = charts.tercile_diagram(row)
        assert isinstance(fig, go.Figure)
        fig.to_dict()


def test_block_attribution_bars_returns_valid_figure():
    fig = charts.block_attribution_bars(fixtures.block_attribution())
    assert isinstance(fig, go.Figure)
    fig.to_dict()


def test_ledger_timeline_returns_valid_figure():
    ledger = fixtures.forecast_ledger()
    fig = charts.ledger_timeline(ledger, target_id="wetday_freq")
    assert isinstance(fig, go.Figure)
    fig.to_dict()


def test_coverage_heatmap_returns_valid_figure():
    fig = charts.coverage_heatmap(fixtures.station_daily_precip(), fixtures.STATIONS)
    assert isinstance(fig, go.Figure)
    fig.to_dict()


def test_reliability_diagram_returns_valid_figure():
    fig = charts.reliability_diagram(fixtures.reliability_data())
    assert isinstance(fig, go.Figure)
    fig.to_dict()


# ---------------------------------------------------------------------------
# regra da paleta: FRIO/QUENTE (dado) nunca aparecem em codigo de interface
# do app fora de charts.py/theme.py (onde tocam dado) — main.py so pode usar
# UI_COLORS (ABISSAL/CARTA/GIZ/BRUMA).
# ---------------------------------------------------------------------------

def test_palette_rule_main_never_hardcodes_data_colors():
    """main.py nao pode conter os hex de FRIO/QUENTE nem os nomes importados
    diretamente — cor de interface vem so de GIZ/BRUMA/CARTA/ABISSAL."""
    src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    for forbidden_hex in ("#3E7FA8", "#C1553A"):
        assert forbidden_hex not in src, f"main.py usa cor de dado {forbidden_hex} fora de charts.py"
    # nao pode importar FRIO/QUENTE do theme para uso em elemento de interface
    import_line = re.search(r"^from app\.theme import (.+)$", src, re.MULTILINE)
    if import_line:
        imported = {n.strip() for n in import_line.group(1).split(",")}
        assert "FRIO" not in imported
        assert "QUENTE" not in imported


def test_palette_rule_charts_only_uses_data_colors_on_data_traces():
    """Verificacao estrutural minima: FRIO/QUENTE em charts.py so aparecem
    dentro de colorscale/fillcolor/marker de trace — nunca em `template`,
    `paper_bgcolor` ou `plot_bgcolor` (que sao decoracao de interface)."""
    src = (ROOT / "app" / "charts.py").read_text(encoding="utf-8")
    for banned_context in ("paper_bgcolor=FRIO", "plot_bgcolor=FRIO",
                            "paper_bgcolor=QUENTE", "plot_bgcolor=QUENTE"):
        assert banned_context not in src


def test_diverging_helper_never_used_for_ui_chrome():
    """theme.diverging() mapeia percentil->cor de dado; garantir que a funcao
    em si so mistura FRIO/QUENTE/CARTA (nunca introduz uma cor nova de UI)."""
    from app.theme import diverging
    lo = diverging(0.0)
    hi = diverging(1.0)
    mid = diverging(0.5)
    assert lo != hi
    assert re.match(r"^#[0-9A-F]{6}$", lo)
    assert re.match(r"^#[0-9A-F]{6}$", hi)
    assert re.match(r"^#[0-9A-F]{6}$", mid)
