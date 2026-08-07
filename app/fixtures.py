"""Gerador de dados SINTETICOS, deterministico (seed fixa), para o front (§9.1/§9.2).

Por que este arquivo existe: o front precisa ser visivel HOJE, mas nenhum dado
real chegou ainda (Fase 1 esta ⬜ no README). A alternativa a fixtures seria um
front vazio ate a ingestao terminar — o que impede revisar design, paleta e
legibilidade da Regua de Surpresa antes que o dado real exista. A troca para
dado real e automatica (ver `app/data_source.py` via `resolve_*`): assim que
`data/interim` ou `data/features` tiverem os parquets esperados, o front usa
eles e o selo "DADO SINTETICO" desaparece. Ninguem pode confundir os dois
porque o selo e visivel em toda visao que consome fixtures.

Todo dado aqui respeita o esquema de `src/contracts.py` (SERIES_COLUMNS) para
que trocar fixtures por dado real seja apenas trocar a fonte, nunca o formato
consumido pelos graficos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.contracts import AnchorMode, QualityFlag

SEED = 20260807  # data do pre-registro (§ decisions.md) — fixa por convencao do projeto

# ---------------------------------------------------------------------------
# ONI mensal 1950-2026, com ciclo ENSO plausivel (quase-periodico 2-7 anos) e
# El Nino ativo em 2026 subindo ate ~+0.7 (consistente com o contexto do
# projeto: "El Nino ativo em 2026 chegando a ~+0.7 e subindo").
# ---------------------------------------------------------------------------


def _oni_series(rng: np.random.Generator) -> pd.DataFrame:
    months = pd.date_range("1950-01-01", "2026-07-01", freq="MS")
    n = len(months)
    t = np.arange(n)
    # Soma de dois cossenos quase-periodicos (~3.5 e ~5.2 anos) + ruido AR(1)
    # baixo-passo -> imita a irregularidade real do ENSO sem ser um modelo real.
    cycle = 0.75 * np.sin(2 * np.pi * t / 42) + 0.45 * np.sin(2 * np.pi * t / 62 + 1.3)
    noise = np.zeros(n)
    phi = 0.85
    innov = rng.normal(0, 0.28, n)
    for i in range(1, n):
        noise[i] = phi * noise[i - 1] + innov[i]
    oni = cycle + noise
    oni = 1.4 * (oni - oni.mean()) / oni.std()  # normaliza amplitude tipica de ONI

    # Forca a cauda 2026 para um El Nino ativo e subindo ate ~+0.7, conforme
    # o contexto de negocio do projeto (nao e projecao real, e enredo sintetico).
    tail_mask = months >= "2025-10-01"
    n_tail = tail_mask.sum()
    ramp = np.linspace(0.35, 0.72, n_tail)
    oni[tail_mask] = ramp + rng.normal(0, 0.03, n_tail)

    return pd.DataFrame({"timestamp": months, "value": oni.round(3)})


def _sam_series(rng: np.random.Generator) -> pd.DataFrame:
    months = pd.date_range("1950-01-01", "2026-07-01", freq="MS")
    n = len(months)
    t = np.arange(n)
    # SAM: tendencia positiva de fundo (forcante ozonio/GEE, §feature_blocks
    # bloco `trend`) + variabilidade rapida, amplamente independente do ENSO.
    trend = 0.012 * (t / 12)
    fast = rng.normal(0, 0.9, n)
    ar = np.zeros(n)
    for i in range(1, n):
        ar[i] = 0.4 * ar[i - 1] + fast[i]
    sam = trend + 0.6 * ar
    return pd.DataFrame({"timestamp": months, "value": sam.round(3)})


def _satl_series(rng: np.random.Generator) -> pd.DataFrame:
    months = pd.date_range("1950-01-01", "2026-07-01", freq="MS")
    n = len(months)
    t = np.arange(n)
    seasonal = 0.3 * np.sin(2 * np.pi * t / 12)
    slow = np.zeros(n)
    innov = rng.normal(0, 0.15, n)
    for i in range(1, n):
        slow[i] = 0.92 * slow[i - 1] + innov[i]
    satl = seasonal + slow
    return pd.DataFrame({"timestamp": months, "value": satl.round(3)})


def _as_series_df(raw: pd.DataFrame, signal_id: str, anchor_mode: str) -> pd.DataFrame:
    """Empacota uma serie mensal bruta no esquema unico de contracts.py."""
    out = raw.copy()
    out["signal_id"] = signal_id
    out["source_version"] = "fixtures_v1"
    out["quality_flag"] = int(QualityFlag.OK)
    out["anchor_mode"] = anchor_mode
    return out[["signal_id", "timestamp", "value", "source_version", "quality_flag", "anchor_mode"]]


def oni_monthly() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    return _as_series_df(_oni_series(rng), "oni", AnchorMode.RELATIVE)


def sam_monthly() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 1)
    return _as_series_df(_sam_series(rng), "sam_cpc", AnchorMode.FIXED)


def satl_monthly() -> pd.DataFrame:
    rng = np.random.default_rng(SEED + 2)
    return _as_series_df(_satl_series(rng), "satl_sst", AnchorMode.RELATIVE)


# ---------------------------------------------------------------------------
# Estacoes do RS — chuva diaria 1961-2026. Poucas estacoes emblematicas,
# nomes plausiveis (nao sao coordenadas reais de INMET, apenas rotulos).
# ---------------------------------------------------------------------------

STATIONS = [
    {"id": "porto_alegre", "label": "Porto Alegre", "automatic_from": "2007-01-01"},
    {"id": "santa_maria", "label": "Santa Maria", "automatic_from": "2003-06-01"},
    {"id": "bage", "label": "Bage", "automatic_from": "2008-11-01"},
    {"id": "passo_fundo", "label": "Passo Fundo", "automatic_from": "2005-03-01"},
    {"id": "sao_borja", "label": "Sao Borja", "automatic_from": "2010-01-01"},
]


def station_daily_precip() -> pd.DataFrame:
    """Chuva diaria sintetica 1961-2026, 5 estacoes do RS.

    Modela sazonalidade (chuva mais intensa na primavera/verao no RS),
    ocorrencia de dia umido via processo de Markov (persistencia realista de
    sequencias de chuva) e intensidade via Gamma condicional ao dia umido.
    Introduz lacunas (quality_flag=INVALID, value=NaN) para exercitar o mapa
    de cobertura, e reduz levemente o ruido apos a transicao automatica do
    INMET (§ visao Saude dos dados) para simular a quebra de homogeneidade.
    """
    dates = pd.date_range("1961-01-01", "2026-07-31", freq="D")
    doy = dates.dayofyear.values
    frames = []
    for k, st in enumerate(STATIONS):
        rng = np.random.default_rng(SEED + 10 + k)
        n = len(dates)
        # sazonalidade: pico OND/verao, minimo inverno — tipico regime subtropical
        seasonal_wet_p = 0.34 + 0.10 * np.sin(2 * np.pi * (doy - 60) / 365.0)
        wet = np.zeros(n, dtype=bool)
        wet[0] = rng.random() < seasonal_wet_p[0]
        for i in range(1, n):
            p_wet_given_wet = min(0.75, seasonal_wet_p[i] + 0.35)
            p_wet_given_dry = max(0.10, seasonal_wet_p[i] - 0.15)
            p = p_wet_given_wet if wet[i - 1] else p_wet_given_dry
            wet[i] = rng.random() < p

        automatic_from = pd.Timestamp(st["automatic_from"])
        shape = np.where(dates >= automatic_from, 1.15, 1.00)  # leve mudanca de regime de medida
        intensity = rng.gamma(shape=shape, scale=9.0) * (1.0 + 0.4 * np.sin(2 * np.pi * (doy - 60) / 365.0).clip(min=0))
        value = np.where(wet, intensity, 0.0)

        quality = np.full(n, int(QualityFlag.OK), dtype=np.int8)
        # dado convencional (pre-automatica) tem mais suspeitos/interpolados
        pre_auto = dates < automatic_from
        suspect_p = np.where(pre_auto, 0.015, 0.004)
        r = rng.random(n)
        quality[r < suspect_p] = int(QualityFlag.SUSPECT)
        interp_p = np.where(pre_auto, 0.01, 0.002)
        r2 = rng.random(n)
        quality[(r2 < interp_p) & (quality == QualityFlag.OK)] = int(QualityFlag.INTERPOLATED)

        # lacunas reais: blocos de dias INVALID / NaN, mais comuns no periodo
        # convencional — imita falha de observador / pluviografo emperrado.
        n_gaps = rng.integers(3, 9) if pre_auto.any() else rng.integers(0, 3)
        gap_len_choices = rng.integers(2, 25, size=n_gaps)
        gap_starts = rng.integers(0, n - 30, size=n_gaps)
        invalid_mask = np.zeros(n, dtype=bool)
        for gs, gl in zip(gap_starts, gap_len_choices):
            invalid_mask[gs:gs + gl] = True
        quality[invalid_mask] = int(QualityFlag.INVALID)
        value = np.where(invalid_mask, np.nan, value)

        frames.append(pd.DataFrame({
            "signal_id": f"prcp_{st['id']}",
            "timestamp": dates,
            "value": value.round(1),
            "source_version": "fixtures_v1",
            "quality_flag": quality,
            "anchor_mode": AnchorMode.FIXED,
        }))
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Ledger de previsoes de exemplo — append-only por design real; aqui apenas
# um historico sintetico plausivel de emissoes OND 1991-2025, com o trio de
# alvos, e observado preenchido para anos passados (2026 fica em aberto).
# ---------------------------------------------------------------------------

TARGET_IDS = ["wetday_freq", "wetday_intensity", "p95_daily"]
TARGET_LABELS = {
    "wetday_freq": "Frequencia de dias umidos",
    "wetday_intensity": "Intensidade em dia umido",
    "p95_daily": "P95 diario",
}
TERCILE_LABELS = ["Abaixo", "Perto da norma", "Acima"]


def forecast_ledger() -> pd.DataFrame:
    """Previsoes OND emitidas 1991-2025 vs observado — climatologia vigente.

    Consistente com ADR-007 (§manifests/feature_blocks.yaml): enquanto nenhum
    modelo passa no limite inferior do IC 90% de RPSS, a previsao emitida E a
    climatologia (tercis ~33/33/33 com leve ruido de amostragem), nao um
    modelo ajustado. O ledger sintetico reflete isso: nao ha "acerto" artificial.
    """
    rng = np.random.default_rng(SEED + 99)
    years = np.arange(1991, 2026)
    rows = []
    for y in years:
        issued = pd.Timestamp(f"{y}-09-30")  # leakage_cutoff do feature_blocks
        for tid in TARGET_IDS:
            probs = rng.dirichlet(alpha=[7, 7, 7])  # perto de climatologia, ruido de amostra
            observed_tercile = int(rng.choice([0, 1, 2], p=[0.33, 0.34, 0.33]))
            rows.append({
                "season": f"OND{y}",
                "target_id": tid,
                "target_label": TARGET_LABELS[tid],
                "issued_at": issued,
                "p_below": round(float(probs[0]), 3),
                "p_near": round(float(probs[1]), 3),
                "p_above": round(float(probs[2]), 3),
                "predicted_tercile": int(np.argmax(probs)),
                "observed_tercile": observed_tercile,
                "climatology_is_forecast": True,  # ADR-007: nenhum modelo aceito ainda
                "rpss_lower_ci90": round(float(rng.normal(-0.03, 0.02)), 4),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Estado atual (Regua de Surpresa) — percentil causal + trilha de 12 meses
# por variavel/bloco, derivado das series sinteticas acima para coerencia
# interna (o percentil de ONI realmente vem da serie de ONI sintetica etc).
# ---------------------------------------------------------------------------

def _causal_percentile(values: np.ndarray) -> np.ndarray:
    """Percentil causal simples: rank contra tudo ATE o instante (resolucao 1/t).

    Deliberadamente ingenuo (nao e o operador real da Camada 3) — serve so
    para o front ter uma trilha plausivel e coerente com a serie sintetica.
    """
    out = np.empty(len(values))
    for i in range(len(values)):
        window = values[: i + 1]
        out[i] = (window <= values[i]).sum() / len(window)
    return out


def surprise_state() -> pd.DataFrame:
    oni = oni_monthly()
    sam = sam_monthly()
    satl = satl_monthly()

    channels = [
        ("oni_lag1", "ONI (Estado ENSO)", oni, AnchorMode.RELATIVE),
        ("oni_innovation_jas", "Dinamica ENSO (inovacao)", oni, AnchorMode.RELATIVE),
        ("sam_cpc_son", "SAM", sam, AnchorMode.FIXED),
        ("satl_coastal_sst_lag1", "TSM Atlantico Sul", satl, AnchorMode.RELATIVE),
        ("year_index", "Tendencia", oni, AnchorMode.FIXED),
    ]
    rows = []
    for signal_id, label, series, anchor in channels:
        vals = series["value"].to_numpy()
        if signal_id == "oni_innovation_jas":
            vals = np.diff(vals, prepend=vals[0])  # residuo simples como proxy de "inovacao"
        if signal_id == "year_index":
            vals = np.arange(len(vals), dtype=float)  # tendencia monotona -> percentil ~1.0 no fim
        pct = _causal_percentile(vals)
        rows.append({
            "signal_id": signal_id,
            "label": label,
            "percentile": float(pct[-1]),
            "trail_12m": [float(x) for x in pct[-12:]],
            "anchor_mode": anchor,
            "value_current": float(vals[-1]),
        })
    return pd.DataFrame(rows)


def block_attribution() -> pd.DataFrame:
    """Atribuicao por bloco (barras) + contrafactual 'removendo ENSO'.

    Sintetico mas com hierarquia plausivel: ENSO domina (20-35% de variancia
    explicada, conforme rationale do bloco `enso_state` em feature_blocks.yaml).
    """
    rng = np.random.default_rng(SEED + 5)
    blocks = ["enso_state", "enso_dynamics", "sam", "satl", "trend"]
    labels = ["Estado ENSO", "Dinamica ENSO", "SAM", "Atlantico Sul", "Tendencia"]
    base = np.array([0.29, 0.11, 0.17, 0.09, 0.06])
    noise = rng.normal(0, 0.01, len(base))
    full = np.clip(base + noise, 0, None)
    counterfactual = full.copy()
    counterfactual[0] = 0.0  # remove ENSO (estado)
    counterfactual[1] = 0.0  # remove ENSO (dinamica)
    return pd.DataFrame({
        "block_id": blocks,
        "label": labels,
        "share_full": full,
        "share_without_enso": counterfactual,
    })


def target_forecast_vs_climatology() -> pd.DataFrame:
    """Diagrama de tercis: previsao vs climatologia para o trio de alvos, com IC.

    Como nenhum modelo foi aceito (ADR-007), 'previsao' aqui e a climatologia
    perturbada por ruido de amostra pequeno — nao um resultado de skill.
    """
    rng = np.random.default_rng(SEED + 6)
    rows = []
    for tid in TARGET_IDS:
        clim = np.array([1 / 3, 1 / 3, 1 / 3])
        fc = np.clip(clim + rng.normal(0, 0.02, 3), 0.05, None)
        fc = fc / fc.sum()
        se = 0.05  # ordem de grandeza citada no README (SE(RPSS) 0.10-0.15 -> IC largo)
        rows.append({
            "target_id": tid,
            "target_label": TARGET_LABELS[tid],
            "climatology": clim.tolist(),
            "forecast": fc.tolist(),
            "forecast_se": se,
        })
    return pd.DataFrame(rows)


def reliability_data() -> pd.DataFrame:
    """Diagrama de confiabilidade sintetico: bins de probabilidade previstas
    vs frequencia observada, proximo da diagonal (climatologia bem calibrada
    por construcao), com leve dispersao amostral — n pequeno (36 anos).
    """
    rng = np.random.default_rng(SEED + 7)
    bins = np.linspace(0.1, 0.9, 9)
    observed = bins + rng.normal(0, 0.06, len(bins))
    observed = np.clip(observed, 0, 1)
    n_per_bin = rng.integers(3, 9, len(bins))
    return pd.DataFrame({
        "bin_center": bins,
        "predicted": bins,
        "observed": observed,
        "n": n_per_bin,
    })
