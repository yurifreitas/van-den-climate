"""Territorios tradicionais x memoria hidrica x acesso.

A pergunta
==========

Quem vive onde a agua tem precedente de voltar — e a que distancia esta o
socorro.

Ribeirinho, quilombola e indigena ocupam desproporcionalmente varzea e
margem, por historia de ocupacao e nao por acaso: foram os terrenos que
sobraram. Varzea e exatamente o que a memoria hidrica do JRC identifica como
"ja foi agua e deixou de ser". Cruzar os dois nao e exercicio — e a unica
forma, com dado publico, de nomear onde a exposicao se concentra em populacao
que ja tem menos acesso a Estado.

O QUE ESTE MODULO MEDE, E COM QUE HONESTIDADE
=============================================

Para cada territorio mapeado:

    memoria hidrica    fracao da area do territorio que foi agua entre 1984 e
                       2021 e hoje nao e (JRC)
    agua atual         fracao que e agua permanente ou sazonal hoje
    regime             lagunar / fluvial com remanso / fluvial (ANA), pelo
                       municipio que contem o centroide
    acesso             km ate o hospital ou pronto-socorro mais proximo (CNES)

O QUE ELE NAO MEDE, E POR QUE IMPORTA DIZER
===========================================

**Populacao.** O poligono nao traz quantas pessoas vivem ali. Sem o setor
censitario do Censo 2022 — nao ingerido — nao ha como converter area exposta
em gente exposta, e a diferenca entre as duas e enorme num territorio de
milhares de hectares.

**Territorio nao mapeado.** Comunidade sem processo aberto nao tem poligono e
nao aparece aqui. O vies e sistematico e conhecido: quem tem menos acesso a
Estado tem menos chance de estar mapeado. Um vazio neste mapa e mais provavel
de significar ausencia de politica fundiaria do que ausencia de comunidade —
e ler ao contrario inverte exatamente a realidade que o dado registra.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

TERRITORIOS_PARQUET = INTERIM / "territorios_rs.parquet"
GRADE_NPZ = INTERIM / "jrc_gsw_rs_grade.npz"
BACIAS_PARQUET = INTERIM / "ana_bacias.parquet"
CNES_PARQUET = INTERIM / "cnes_rs.parquet"
MALHA_GEOJSON = INTERIM / "ibge_malha_rs.geojson"

VERSION = "territorios-v1"

# Fracao de memoria hidrica a partir da qual o territorio entra na lista de
# atencao. Mesmo limiar do plano municipal (5%), para que as duas listas
# sejam comparaveis — mudar aqui e nao la criaria dois conceitos com o mesmo
# nome.
LIMIAR_MEMORIA = 0.05


@dataclass(frozen=True)
class TerritoriosResult:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]


def _haversine(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


def _municipio_do_ponto(lon: float, lat: float, malha: dict) -> int | None:
    """Ray casting simples — 40 territorios x 497 poligonos nao pede indice."""
    def aneis(g: dict) -> list:
        return g["coordinates"] if g["type"] == "Polygon" else [
            a for p in g["coordinates"] for a in p
        ]

    for f in malha["features"]:
        for anel in aneis(f["geometry"]):
            dentro = False
            n = len(anel)
            j = n - 1
            for i in range(n):
                xi, yi = anel[i][0], anel[i][1]
                xj, yj = anel[j][0], anel[j][1]
                if (yi > lat) != (yj > lat):
                    if lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                        dentro = not dentro
                j = i
            if dentro:
                return int(f["properties"]["codarea"])
    return None


def build() -> TerritoriosResult:
    if not TERRITORIOS_PARQUET.exists():
        raise FileNotFoundError(
            f"{TERRITORIOS_PARQUET} ausente — rode `python -m src.ingest.territorios`"
        )
    terr = pd.read_parquet(TERRITORIOS_PARQUET)

    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    z = np.load(GRADE_NPZ, allow_pickle=True)
    meta = json.loads(z["meta"][0])
    b = meta["bbox"]
    transform = from_origin(b["lon_min"], b["lat_max"], meta["res_saida"], meta["res_saida"])
    n_px = meta["fator"] ** 2
    cats = {c: z[f"count_{c}"] for c in ("permanente", "sazonal", "perdida", "efemera")}

    malha = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    bacias = pd.read_parquet(BACIAS_PARQUET) if BACIAS_PARQUET.exists() else None
    regime_por_cod = (
        {int(r["cod_mun"]): r["regime"] for _, r in bacias.iterrows()} if bacias is not None else {}
    )
    mun_nome = {
        int(f["properties"]["codarea"]): None for f in malha["features"]
    }
    munic = pd.read_parquet(INTERIM / "ibge_munic_rs.parquet")[["cod_mun", "municipio"]]
    for _, r in munic.iterrows():
        mun_nome[int(r["cod_mun"])] = r["municipio"]

    cnes = pd.read_parquet(CNES_PARQUET) if CNES_PARQUET.exists() else None
    if cnes is not None:
        urg = cnes[cnes["papel"].isin(["fixo_hospitalar", "fixo_urgencia"])].dropna(
            subset=["lat", "lon"]
        )
        ulon = urg["lon"].to_numpy(dtype=float)
        ulat = urg["lat"].to_numpy(dtype=float)
    else:
        ulon = ulat = np.array([])

    rows: list[dict[str, Any]] = []
    for _, t in terr.iterrows():
        geom = json.loads(t["geometria"])
        mask = rasterize(
            [(geom, 1)], out_shape=(meta["n_lat"], meta["n_lon"]),
            transform=transform, fill=0, dtype="uint8", all_touched=True,
        ).astype(bool)
        n_celulas = int(mask.sum())

        fracs: dict[str, float | None] = {}
        if n_celulas:
            for cat, arr in cats.items():
                fracs[cat] = round(float(arr[mask].sum() / (n_celulas * n_px)), 5)
        else:
            fracs = {c: None for c in cats}

        memoria = (
            round((fracs["perdida"] or 0) + (fracs["efemera"] or 0), 5) if n_celulas else None
        )
        agua_hoje = (
            round((fracs["permanente"] or 0) + (fracs["sazonal"] or 0), 5) if n_celulas else None
        )

        cod = _municipio_do_ponto(float(t["lon"]), float(t["lat"]), malha)
        km_urg = (
            round(float(_haversine(float(t["lon"]), float(t["lat"]), ulon, ulat).min()), 1)
            if ulon.size else None
        )

        rows.append({
            "tipo": t["tipo"],
            "nome": t["nome"],
            "grupo_etnico": t["grupo_etnico"],
            "situacao_juridica": t["situacao_juridica"],
            "area_legal_ha": None if pd.isna(t["area_legal_ha"]) else float(t["area_legal_ha"]),
            "cod_mun": cod,
            "municipio": mun_nome.get(cod) if cod else None,
            "regime": regime_por_cod.get(cod) if cod else None,
            "agua": {
                **fracs,
                "memoria_hidrica_frac": memoria,
                "agua_atual_frac": agua_hoje,
                "n_celulas_grade": n_celulas,
                "basis": "measured" if n_celulas else None,
            },
            "km_ate_urgencia": km_urg,
            "atencao_memoria": bool(memoria is not None and memoria >= LIMIAR_MEMORIA),
        })

    rows.sort(key=lambda r: -(r["agua"]["memoria_hidrica_frac"] or 0))

    com_mem = [r for r in rows if r["atencao_memoria"]]
    kms = [r["km_ate_urgencia"] for r in rows if r["km_ate_urgencia"] is not None]
    resumo = {
        "version": VERSION,
        "n_territorios": len(rows),
        "por_tipo": pd.Series([r["tipo"] for r in rows]).value_counts().to_dict(),
        "n_com_memoria_hidrica": len(com_mem),
        "limiar_memoria": LIMIAR_MEMORIA,
        "km_ate_urgencia": {
            "mediana": round(float(np.median(kms)), 1) if kms else None,
            "max": round(float(np.max(kms)), 1) if kms else None,
        },
        "por_regime": pd.Series([r["regime"] for r in rows]).value_counts(dropna=False).to_dict(),
        "limites": [
            "NAO conta pessoas: o poligono nao traz populacao. Converter area exposta em gente "
            "exposta exige o setor censitario do Censo 2022, nao ingerido.",
            "Territorio nao mapeado nao aparece. O vies e sistematico: quem tem menos acesso a "
            "Estado tem menos chance de estar mapeado — um vazio aqui provavelmente significa "
            "ausencia de politica fundiaria, nao ausencia de comunidade.",
            "`situacao_juridica` distingue regularizada de em estudo: mesmo poligono, "
            "realidades opostas em conflito fundiario.",
            "Memoria hidrica cobre 1984-2021 e nao conhece a cheia de 2024.",
            "Distancia e linha reta ao centroide do territorio, nunca rota.",
        ],
    }
    return TerritoriosResult(rows=rows, resumo=resumo)
