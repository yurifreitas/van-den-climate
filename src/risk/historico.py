"""Historia longa da chuva no RS, e o que ela diz sobre El Nino.

=============================================================================
AVISO DE CONTATO COM O ALVO — LEIA ANTES DE MEXER EM feature_blocks.yaml
=============================================================================

A ADR-004 congelou `feature_blocks.yaml` em 2026-08-07 com `target_contact:
false`, e a razao era exatamente esta: enquanto ninguem tivesse olhado o alvo,
a regra de reducao de features nao poderia ser escolhida em funcao dele.

**Este modulo olha o alvo.** Ele calcula o trio da ADR-002 (frequencia de dias
umidos, intensidade em dia umido, p95 diario) na estacao OND, a partir de
chuva diaria observada, e o cruza com o ONI.

A consequencia e imediata e nao negociavel: **a partir daqui, mudar
`feature_blocks.yaml` invalida o experimento** (Invariante 6 do README). O
arquivo esta congelado de fato, nao so por promessa.

O que este modulo E: analise DESCRITIVA da relacao historica. Quantos anos, com
que sinal, com que dispersao.

O que este modulo NAO E, e nao pode virar sem passar pela ADR-007: selecao de
preditor, ajuste de modelo, ou qualquer escolha feita "porque o numero ficou
melhor". Nao ha ajuste aqui — ha contagem.

=============================================================================

Janela e cobertura
==================

As series brasileiras do GHCN-Daily terminam entre 1997 e 1999. Com ONI a
partir de 1950, a interseccao util e ~1950-1999: cerca de cinquenta primaveras,
o que e muito mais que os n=36 da avaliacao pre-registrada, e mesmo assim
pouco para extremo.

A camada NAO cobre 2024. Isso e uma qualidade para o cruzamento — como no
JRC, a historia nao conhece o evento — e uma limitacao para monitoramento: ela
nao diz nada sobre a estacao corrente.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

DIARIO = INTERIM / "ghcn_rs_diario.parquet"
ESTACOES = INTERIM / "ghcn_rs_estacoes.parquet"
ONI_PARQUET = INTERIM / "cpc_oni.parquet"

VERSION = "historico-v1"

# Estacao-alvo do projeto: outubro-novembro-dezembro (ADR-002).
MESES_OND = (10, 11, 12)
DIAS_OND = 92
# Cobertura minima para a temporada contar. 80 de 92 dias: com menos que isso
# a frequencia de dias umidos vira funcao de quantos dias faltam, nao de chuva.
MIN_DIAS = 80
# Limiar de dia umido. 1 mm e a convencao da OMM — abaixo disso o registro
# confunde chuva com orvalho e erro de leitura de pluviometro.
LIMIAR_UMIDO = 1.0

# Classificacao ENSO pelo ONI da propria estacao OND, mesmos limiares
# operacionais do CPC usados no resto do projeto.
LIMIAR_ENSO = 0.5


@dataclass(frozen=True)
class HistoricoResult:
    por_estacao_ano: pd.DataFrame
    por_ano: pd.DataFrame
    composto: dict[str, Any]
    meta: dict[str, Any]


def _oni_ond() -> pd.Series:
    """ONI da estacao OND por ano (media de out, nov, dez)."""
    if not ONI_PARQUET.exists():
        return pd.Series(dtype=float)
    oni = pd.read_parquet(ONI_PARQUET)
    oni = oni[oni["signal_id"] == "oni"].copy()
    oni["timestamp"] = pd.to_datetime(oni["timestamp"])
    ond = oni[oni["timestamp"].dt.month.isin(MESES_OND)]
    return ond.groupby(ond["timestamp"].dt.year)["value"].mean()


def _trio(serie: pd.Series) -> dict[str, float]:
    """O trio da ADR-002 para uma temporada de uma estacao.

    p95 sobre TODOS os dias, nao so os umidos: o alvo e o extremo diario da
    estacao, e condicionar em dia umido removeria justamente a informacao de
    quantos dias secos separam os eventos.
    """
    umidos = serie[serie >= LIMIAR_UMIDO]
    return {
        "freq_dias_umidos": float(len(umidos) / len(serie)),
        "intensidade_mm": float(umidos.mean()) if len(umidos) else 0.0,
        "p95_mm": float(np.percentile(serie, 95)),
        "total_mm": float(serie.sum()),
        "n_dias": int(len(serie)),
    }


def calcular() -> HistoricoResult:
    if not DIARIO.exists():
        raise FileNotFoundError(f"{DIARIO} ausente — rode `python -m src.ingest.ghcn_rs`")
    diario = pd.read_parquet(DIARIO)
    estacoes = pd.read_parquet(ESTACOES)

    diario["ano"] = diario["data"].dt.year
    ond = diario[diario["data"].dt.month.isin(MESES_OND)]

    linhas = []
    for (sid, ano), grupo in ond.groupby(["station_id", "ano"]):
        if len(grupo) < MIN_DIAS:
            continue  # temporada incompleta nao entra: ver MIN_DIAS
        linhas.append({"station_id": sid, "ano": int(ano), **_trio(grupo["prcp_mm"])})
    por_estacao_ano = pd.DataFrame(linhas)
    if por_estacao_ano.empty:
        raise ValueError("nenhuma temporada OND com cobertura suficiente")

    por_estacao_ano = por_estacao_ano.merge(
        estacoes[["station_id", "nome", "lat", "lon", "cod_mun"]], on="station_id", how="left"
    )

    # Media entre estacoes por ano: um indice ESTADUAL do trio. Media simples,
    # nao ponderada por area — a rede nao e um grid e fingir que e, via
    # interpolacao, adicionaria uma suposicao que este modulo nao precisa.
    por_ano = (
        por_estacao_ano.groupby("ano")
        .agg(
            n_estacoes=("station_id", "nunique"),
            freq_dias_umidos=("freq_dias_umidos", "mean"),
            intensidade_mm=("intensidade_mm", "mean"),
            p95_mm=("p95_mm", "mean"),
            total_mm=("total_mm", "mean"),
        )
        .reset_index()
    )

    oni = _oni_ond()
    por_ano["oni_ond"] = por_ano["ano"].map(oni)
    por_ano["fase"] = np.where(
        por_ano["oni_ond"] >= LIMIAR_ENSO, "El Nino",
        np.where(por_ano["oni_ond"] <= -LIMIAR_ENSO, "La Nina", "Neutro"),
    )
    por_ano.loc[por_ano["oni_ond"].isna(), "fase"] = "sem ONI"

    # Percentil historico de cada ano dentro da propria serie: e assim que o
    # front pode dizer "1997 foi o 2o OND mais umido de 50" sem inventar
    # unidade nenhuma.
    for col in ("freq_dias_umidos", "intensidade_mm", "p95_mm", "total_mm"):
        por_ano[f"pct_{col}"] = por_ano[col].rank(pct=True).round(4)

    composto = _composto_por_fase(por_ano)

    anos_validos = por_ano[por_ano["fase"] != "sem ONI"]
    meta = {
        "version": VERSION,
        "fonte": "GHCN-Daily (NOAA/NCEI), estacoes dentro do poligono do RS",
        "n_estacoes": int(por_estacao_ano["station_id"].nunique()),
        "n_temporadas_estacao": int(len(por_estacao_ano)),
        "periodo": [int(por_ano["ano"].min()), int(por_ano["ano"].max())],
        "periodo_com_oni": (
            [int(anos_validos["ano"].min()), int(anos_validos["ano"].max())]
            if not anos_validos.empty else None
        ),
        "estacao_alvo": "OND (outubro-dezembro)",
        "limiar_dia_umido_mm": LIMIAR_UMIDO,
        "cobertura_minima_dias": MIN_DIAS,
        "contato_com_alvo": (
            "Este calculo E contato com o alvo (ADR-004). A partir dele, mudar "
            "feature_blocks.yaml invalida o experimento."
        ),
        "limites": [
            "Series brasileiras do GHCN-Daily terminam entre 1997 e 1999 — arquivo historico, "
            "nao serie operacional. NAO cobre 2024.",
            "Sem homogeneizacao: a Camada 2 (quebras, troca de sitio e de instrumento) nao foi "
            "construida. Serie longa de estacao tem descontinuidade quase por definicao.",
            "Media simples entre estacoes, sem ponderacao por area: a rede nao e um grid.",
            "Analise DESCRITIVA. Nenhum modelo foi ajustado e nenhum preditor foi selecionado "
            "aqui — isso exigiria passar pelo criterio da ADR-007.",
        ],
    }
    return HistoricoResult(por_estacao_ano, por_ano, composto, meta)


def _composto_por_fase(por_ano: pd.DataFrame) -> dict[str, Any]:
    """Distribuicao do trio por fase ENSO, com IC por bootstrap.

    Bootstrap e nao teste-t: n por fase e de uma a duas dezenas, e a
    distribuicao de p95 nao e normal. Intervalo por reamostragem nao supoe
    forma. Semente fixa para que o numero na tela nao mude entre recargas.
    """
    rng = np.random.default_rng(20260807)
    saida: dict[str, Any] = {"limiar_oni": LIMIAR_ENSO, "fases": {}}

    for fase in ("El Nino", "Neutro", "La Nina"):
        sub = por_ano[por_ano["fase"] == fase]
        if sub.empty:
            continue
        metricas: dict[str, Any] = {"n_anos": int(len(sub)), "anos": [int(a) for a in sub["ano"]]}
        for col in ("freq_dias_umidos", "intensidade_mm", "p95_mm", "total_mm"):
            v = sub[col].to_numpy()
            reamostras = rng.choice(v, size=(2000, len(v)), replace=True).mean(axis=1)
            metricas[col] = {
                "media": round(float(v.mean()), 4),
                "ic90": [round(float(np.percentile(reamostras, 5)), 4),
                         round(float(np.percentile(reamostras, 95)), 4)],
            }
        saida["fases"][fase] = metricas

    # Deslocamento El Nino - Neutro, com IC do proprio deslocamento. E este
    # numero — nao a media de cada fase — que responde "El Nino molha o RS?".
    en = por_ano[por_ano["fase"] == "El Nino"]
    ne = por_ano[por_ano["fase"] == "Neutro"]
    if not en.empty and not ne.empty:
        desloc: dict[str, Any] = {}
        for col in ("freq_dias_umidos", "intensidade_mm", "p95_mm", "total_mm"):
            a, b = en[col].to_numpy(), ne[col].to_numpy()
            ra = rng.choice(a, size=(2000, len(a)), replace=True).mean(axis=1)
            rb = rng.choice(b, size=(2000, len(b)), replace=True).mean(axis=1)
            d = ra - rb
            lo, hi = float(np.percentile(d, 5)), float(np.percentile(d, 95))
            desloc[col] = {
                "delta": round(float(a.mean() - b.mean()), 4),
                "ic90": [round(lo, 4), round(hi, 4)],
                # "Separa de zero" = o IC 90% nao cruza zero. E o mesmo espirito
                # do criterio da ADR-007, aplicado a uma diferenca descritiva:
                # sem isso, um delta positivo por acaso vira manchete.
                "separa_de_zero": bool(lo > 0 or hi < 0),
            }
        saida["deslocamento_elnino_vs_neutro"] = desloc
    return saida


def load_json() -> dict[str, Any] | None:
    path = INTERIM / "historico_rs.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run() -> HistoricoResult:
    res = calcular()
    res.por_estacao_ano.to_parquet(INTERIM / "historico_estacao_ano.parquet", index=False)
    res.por_ano.to_parquet(INTERIM / "historico_ano.parquet", index=False)
    (INTERIM / "historico_rs.json").write_text(
        json.dumps(
            {"meta": res.meta, "composto": res.composto,
             "por_ano": json.loads(res.por_ano.to_json(orient="records"))},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return res


if __name__ == "__main__":
    r = run()
    m = r.meta
    print(f"[OK] {m['n_estacoes']} estacoes, {m['n_temporadas_estacao']} temporadas-estacao")
    print(f"     periodo {m['periodo'][0]}–{m['periodo'][1]} (com ONI: {m['periodo_com_oni']})")
    print()
    for fase, d in r.composto["fases"].items():
        print(f"  {fase:9s} n={d['n_anos']:2d}  "
              f"dias umidos {d['freq_dias_umidos']['media']:.3f}  "
              f"p95 {d['p95_mm']['media']:6.2f} mm  "
              f"total {d['total_mm']['media']:7.1f} mm")
    d = r.composto.get("deslocamento_elnino_vs_neutro")
    if d:
        print("\n  El Nino - Neutro (IC90 por bootstrap):")
        for k, v in d.items():
            marca = "SEPARA DE ZERO" if v["separa_de_zero"] else "cruza zero"
            print(f"    {k:20s} {v['delta']:+8.3f}  IC90 [{v['ic90'][0]:+.3f}, {v['ic90'][1]:+.3f}]  {marca}")
