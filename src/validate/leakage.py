"""Gate anti-vazamento (§8.4, ADR-010).

Vazamento temporal e o unico erro que nao aparece na metrica: ele a melhora.
Por isso o gate e um teste bloqueante de CI, nao uma inspecao manual.

Tres verificacoes independentes:
  1. NOMES     — toda feature declara defasagem no nome
  2. TIMESTAMP — nenhum insumo posterior ao corte entra na previsao
  3. PREPROC   — normalizacao/PCA/CDF ajustados apenas dentro do fold
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import pandas as pd

from src.contracts import validate_feature_name

# Previsao de OND/AAAA e emitida em 01/out/AAAA: nada apos 30/set entra.
CUTOFF_MONTH_DAY = (9, 30)


def cutoff_for(target_year: int) -> pd.Timestamp:
    return pd.Timestamp(dt.date(target_year, *CUTOFF_MONTH_DAY))


class LeakageError(AssertionError):
    pass


@dataclass
class FeatureProvenance:
    """Rastro de quais timestamps de insumo entraram no calculo de uma feature.

    Os operadores da Camada 3 populam isto; nao e reconstruivel a posteriori.
    """

    feature: str
    target_year: int
    input_timestamps: list[pd.Timestamp] = field(default_factory=list)
    fitted_on: list[pd.Timestamp] = field(default_factory=list)  # normalizacao/PCA/CDF

    def max_input(self) -> pd.Timestamp | None:
        allts = list(self.input_timestamps) + list(self.fitted_on)
        return max(allts) if allts else None


def check_names(features: list[str]) -> None:
    for f in features:
        validate_feature_name(f)


def check_timestamps(provs: list[FeatureProvenance]) -> None:
    """Verificacao 2 e 3 — inclui o que foi usado para AJUSTAR transformacoes.

    A forma mais comum de vazamento neste projeto nao e usar o valor futuro:
    e ajustar o z-score, a PCA ou a CDF do PIT no conjunto completo.
    """
    violations = []
    for p in provs:
        cut = cutoff_for(p.target_year)
        for label, stamps in (("input", p.input_timestamps), ("fit", p.fitted_on)):
            late = [t for t in stamps if pd.Timestamp(t) > cut]
            if late:
                violations.append(
                    f"{p.feature} (alvo {p.target_year}, corte {cut.date()}): "
                    f"{len(late)} timestamps de {label} apos o corte, "
                    f"o mais tardio {max(late)}"
                )
    if violations:
        raise LeakageError("VAZAMENTO TEMPORAL:\n  " + "\n  ".join(violations))


def check_anchor_isolation(fit_stamps: list[pd.Timestamp], target_year: int) -> None:
    """A ancora 1951-1990 (ADR-001) nunca pode conter o ano-alvo."""
    if any(pd.Timestamp(t).year == target_year for t in fit_stamps):
        raise LeakageError(
            f"ancora de calibracao contem o proprio ano-alvo {target_year}"
        )


def gate(features: list[str], provs: list[FeatureProvenance]) -> None:
    """Ponto unico chamado pelo CI e por todo fold do walk-forward."""
    check_names(features)
    check_timestamps(provs)
    declared = {p.feature for p in provs}
    undeclared = set(features) - declared
    if undeclared:
        raise LeakageError(
            f"features sem proveniencia declarada: {sorted(undeclared)} — "
            "ausencia de rastro nao e prova de ausencia de vazamento"
        )
