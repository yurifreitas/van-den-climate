"""Carrega `manifests/feature_blocks.yaml` e aplica a regra de reducao
PRE-REGISTRADA (ADR-004): por bloco, z-score + 1a componente principal,
ambos ajustados DENTRO do fold (so com dados < corte), com o sinal da PC
fixado pelo `sign_anchor` declarado no manifesto.

Por que o sinal precisa ser fixado manualmente: o SVD nao tem nocao de "El
Nino e positivo" — ele devolve o autovetor a menos de sinal, e o sinal que
sai depende de ruido numerico/amostral. Sem ancorar o sinal a uma variavel
fisica conhecida (`sign_anchor`), a PC positiva significaria "El Nino" num
fold e "La Nina" no fold seguinte, e o modelo supervisionado (Camada 6)
receberia uma feature cujo significado troca por baixo dele. Isso nao
apareceria como erro — apareceria como uma feature com peso perto de zero
(RPSS achatado), i.e. um falso negativo silencioso.

REGRA INEGOCIAVEL do manifesto: nunca escolher n_components pela variancia
observada (esta congelado em 1), nunca rodar PCA no conjunto completo,
nunca reordenar componentes pelo alvo. Este modulo nao expoe nenhum
parametro para violar essas tres coisas.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.contracts import ANCHOR_START
from src.validate.leakage import FeatureProvenance

__all__ = [
    "BlockResult",
    "load_manifest",
    "reduce_block",
    "reduce_all_blocks",
]

DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "manifests" / "feature_blocks.yaml"


@dataclass(frozen=True)
class BlockResult:
    block_id: str
    value: float             # PC1, com sinal fixado
    provenance: FeatureProvenance
    coverage: float           # fracao de sinais do bloco com cobertura suficiente


def load_manifest(path: Path | str = DEFAULT_MANIFEST_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
    n_blocks = len(manifest["blocks"])
    if n_blocks != 5:
        # ADR-003: o numero de preditores da Camada 6 e travado em 5. Um
        # manifesto com numero diferente de blocos e uma violacao de
        # pre-registro, nao um detalhe de implementacao — falha cedo.
        raise ValueError(
            f"feature_blocks.yaml declara {n_blocks} blocos, esperado exatamente 5 (ADR-003)"
        )
    return manifest


def _standardize_in_fold(mat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """z-score coluna a coluna usando so as linhas fornecidas (que ja devem
    ter sido cortadas para < t antes de chegar aqui)."""
    mean = mat.mean(axis=0)
    std = mat.std(axis=0, ddof=0)
    std_safe = np.where(std == 0, 1.0, std)
    z = (mat - mean) / std_safe
    return z, mean, std_safe


def _pc1_via_svd(z: np.ndarray) -> np.ndarray:
    """1a componente principal via SVD (preferida a sklearn.PCA — evita
    dependencia extra e e matematicamente identica para n_components=1).
    z ja deve estar centrado/escalado (linhas=observacoes, colunas=sinais).
    """
    # np.linalg.svd: z = U @ diag(S) @ Vt ; a 1a PC (scores) e U[:,0]*S[0],
    # e a direcao (loadings) e Vt[0]. Aqui devolvemos os scores, que sao o
    # que vira o preditor.
    U, S, Vt = np.linalg.svd(z, full_matrices=False)
    scores = U[:, 0] * S[0]
    return scores


def reduce_block(
    block_cfg: dict,
    signals: dict[str, pd.Series],
    t: pd.Timestamp,
    *,
    target_year: int,
    min_coverage: float = 0.80,
) -> BlockResult:
    """Reduz um bloco a um unico preditor (PC1) usando so observacoes com
    timestamp < t (ou <= ANCHOR_END quando anchor_mode = fixed, ver
    manifesto) para ajustar z-score e SVD — preproc-in-fold.

    `signals` mapeia signal_id -> serie (indice = timestamp). Sinais
    ausentes do dict, ou com cobertura abaixo de `min_coverage` na janela
    de ajuste, sao dropados do bloco (regra do manifesto:
    `missing.drop_signal_if_coverage_below`), NAO preenchidos com zero —
    preencher destruiria a covariancia estimada pela PCA.
    """
    block_id = block_cfg["id"]
    declared_ids = [s["id"] for s in block_cfg["signals"]]
    sign_anchor_id = block_cfg["sign_anchor"]

    anchor_start = pd.Timestamp(ANCHOR_START)
    # Janela de ajuste: expanding desde a ancora ate (exclusive) t. Vale
    # tanto para anchor_mode fixed quanto relative — a diferenca de modo
    # e sobre COMO os sinais brutos foram construidos (Camada 1/2), nao
    # sobre a janela de ajuste do z-score/PCA aqui.
    cols: dict[str, pd.Series] = {}
    used_timestamps: set[pd.Timestamp] = set()
    for sid in declared_ids:
        s = signals.get(sid)
        if s is None:
            continue
        window = s[(s.index >= anchor_start) & (s.index < t)].dropna().sort_index()
        # cobertura = fracao de timestamps esperados (uniao de todos os
        # sinais do bloco) presentes neste sinal; aproximamos usando a
        # contagem simples de pontos disponiveis vs o maior sinal do bloco
        # depois de montarmos `cols` (checagem final abaixo).
        cols[sid] = window

    if not cols:
        raise ValueError(f"bloco {block_id}: nenhum sinal declarado esta disponivel em `signals`")

    # Alinha por intersecao de timestamps (so podemos fazer PCA em linhas
    # completas) — outra razao para dropar sinais de baixa cobertura antes:
    # um unico sinal esparso encolheria a intersecao para quase nada.
    lengths = {sid: len(w) for sid, w in cols.items()}
    max_len = max(lengths.values()) if lengths else 0
    kept = {
        sid: w
        for sid, w in cols.items()
        if max_len > 0 and (len(w) / max_len) >= min_coverage
    }
    if not kept:
        raise ValueError(f"bloco {block_id}: nenhum sinal atinge cobertura minima {min_coverage}")

    df = pd.DataFrame(kept).dropna(how="any")
    coverage = len(kept) / len(declared_ids)

    if len(df) < 3:
        # Historico insuficiente para uma PCA minimamente estavel (menos
        # linhas que colunas+2). Devolve NaN em vez de forcar um numero.
        prov = FeatureProvenance(
            feature=f"{block_id}_pc1",
            target_year=target_year,
            input_timestamps=[],
            fitted_on=list(df.index),
        )
        return BlockResult(block_id, float("nan"), prov, coverage)

    mat = df.values.astype(float)
    z, mean, std = _standardize_in_fold(mat)
    scores = _pc1_via_svd(z)

    # --- sign_anchor: fixa o sinal da PC pela correlacao com a variavel
    # fisica declarada no manifesto (ex.: oni_lag1, PC positiva := El Nino).
    if sign_anchor_id in df.columns:
        anchor_col = z[:, list(df.columns).index(sign_anchor_id)]
        corr = np.corrcoef(scores, anchor_col)[0, 1]
        if np.isnan(corr):
            corr = 0.0
        if corr < 0:
            scores = -scores
    # se o sign_anchor foi dropado por cobertura, o sinal fica indefinido
    # nesta fold — melhor deixar como veio do SVD (documentado) do que
    # inventar uma referencia; isso e raro dado min_coverage=0.80.

    # o valor do bloco NO INSTANTE t e o ultimo score da serie expandida —
    # equivalente a projetar a observacao mais recente (t-1, a ultima
    # disponivel antes do corte) no eixo da PC1 ajustada com esse mesmo
    # historico. Isso mantem o operador causal: value("agora") usa uma PC
    # ajustada so com o passado.
    value = float(scores[-1])

    prov = FeatureProvenance(
        feature=f"{block_id}_pc1",
        target_year=target_year,
        input_timestamps=[],
        fitted_on=list(df.index),  # o que ajustou z-score + SVD
    )
    return BlockResult(block_id, value, prov, coverage)


def reduce_all_blocks(
    signals: dict[str, pd.Series],
    t: pd.Timestamp,
    *,
    target_year: int,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
) -> tuple[dict[str, BlockResult], list[FeatureProvenance]]:
    """Aplica `reduce_block` aos 5 blocos do manifesto e garante que o
    resultado tem exatamente 5 preditores — o numero e travado pela
    ADR-003 e verificado aqui, nao so documentado."""
    manifest = load_manifest(manifest_path)
    results: dict[str, BlockResult] = {}
    provs: list[FeatureProvenance] = []
    for block_cfg in manifest["blocks"]:
        res = reduce_block(block_cfg, signals, t, target_year=target_year)
        results[res.block_id] = res
        provs.append(res.provenance)

    if len(results) != 5:
        raise AssertionError(
            f"reduce_all_blocks devolveu {len(results)} preditores, esperado exatamente 5"
        )
    return results, provs
