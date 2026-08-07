"""PIT (Probability Integral Transform) causal — ranks causais.

Mesmo principio do SPI (Standardized Precipitation Index): transforma um
valor em seu percentil dentro de uma distribuicao empirica de referencia.
A diferenca do SPI convencional (que normalmente ajusta a CDF numa janela
fixa, as vezes olhando o registro inteiro) e que aqui a CDF e SEMPRE
ajustada em `expanding` — so com dados anteriores a t — pelo mesmo motivo
de `operators.surprise`: ajustar a CDF no conjunto completo e o modo de
falha real do projeto (§8.4).

Custo zero em graus de liberdade: PIT nao estima nenhum parametro (nao ha
media/variancia/forma a ajustar como num modelo parametrico) — e so a
posicao empirica do dado dentro do que ja foi observado. Isso o torna
seguro de usar liberalmente mesmo com n pequeno, ao contrario de qualquer
coisa que exija estimar parametros.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.contracts import ANCHOR_START
from src.validate.leakage import FeatureProvenance

__all__ = ["PitResult", "causal_pit"]


@dataclass(frozen=True)
class PitResult:
    pit: float               # rank/CDF causal em (0, 1]
    resolution: float        # 1/t, mesma logica de causal_percentile
    provenance: FeatureProvenance


def causal_pit(
    series: pd.Series,
    t: pd.Timestamp,
    *,
    feature: str,
    target_year: int,
    anchor_start: pd.Timestamp | None = None,
) -> PitResult:
    """PIT causal de x_t: fracao da historia [anchor_start, t) que fica
    <= x_t, com correcao de Hazen (+0.5 no numerador, +1 no denominador)
    para nunca devolver exatamente 0 ou 1 — extremos exatos quebram
    transformacoes posteriores (e.g. logit) e nao sao defensaveis com t
    finito de qualquer forma.

    p_t = (0.5 + #{i < t : x_i <= x_t}) / (t)   , t = |historia| + 1

    Resolucao continua sendo ~1/t: o numero de valores distintos de p_t
    representaveis e limitado pelo tamanho da historia disponivel, entao a
    mesma advertencia do operador Surprise vale aqui — com t pequeno nao da
    para expressar eventos raros.
    """
    anchor_start = anchor_start or pd.Timestamp(ANCHOR_START)
    hist = series[(series.index >= anchor_start) & (series.index < t)].dropna().sort_index()
    x_t = float(series.loc[t]) if t in series.index else np.nan

    t_count = len(hist) + 1
    resolution = 1.0 / t_count

    if np.isnan(x_t) or len(hist) == 0:
        pit_val = float("nan")
    else:
        count_le = int(np.sum(hist.values <= x_t))
        pit_val = (0.5 + count_le) / t_count

    prov = FeatureProvenance(
        feature=feature,
        target_year=target_year,
        input_timestamps=[t] if t in series.index else [],
        fitted_on=list(hist.index),
    )
    return PitResult(pit_val, resolution, prov)
