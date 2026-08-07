"""Estatistica zonal de agua por municipio — a memoria hidrica do territorio.

O que este modulo produz, e por que ele existe separado da ingestao
==================================================================

`src/ingest/jrc_gsw.py` entrega uma grade retangular de contagens. Uma grade
retangular sobre o RS inclui o **oceano Atlantico** e pedacos de Santa
Catarina, Argentina e Uruguai — na primeira execucao o total de "agua
permanente" deu 106.000 km² num estado de 281.000 km², numero que so podia
sair de contar o mar. Este modulo corta a grade pela malha municipal do IBGE
e devolve area por municipio; o total do estado passa a ser a soma dos 497,
que e a unica forma de garantir que nenhum pixel de fora entrou na conta.

As quatro categorias e o que cada uma diz ao gestor
===================================================

    permanente  rio e lago de hoje. E o mapa hidrografico medido por satelite.
    sazonal     varzea e banhado: enche todo ano. Nao e "risco", e regime.
    perdida     ERA agua entre 1984 e 2021 e deixou de ser. Leito abandonado,
                banhado drenado, lago aterrado. E o passivo escondido: terreno
                que a engenharia tratou como seco e a hidrologia nao esqueceu.
    efemera     encheu uma vez dentro da serie e sumiu. Assinatura de evento
                extremo anterior a 2021.

`perdida` + `efemera` e a resposta mais proxima que o dado publico permite
para "areas que voltaram a encher": terreno com precedente de agua, hoje
seco no mapa oficial.

O cruzamento que nao e circular
===============================

A serie do JRC termina em 2021 e nao contem a cheia de maio de 2024. Quando
um municipio com muita agua perdida aparece TAMBEM com inundacao declarada ao
IBGE em 2024, sao duas bases independentes concordando — uma optica, de
satelite, anterior ao evento; outra declaratoria, da prefeitura, posterior.
Se a serie do JRC incluisse 2024 esse cruzamento nao valeria nada.
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

GRADE_NPZ = INTERIM / "jrc_gsw_rs_grade.npz"
MALHA_GEOJSON = INTERIM / "ibge_malha_rs.geojson"
SAIDA_PARQUET = INTERIM / "aguas_municipios.parquet"
SAIDA_PNG = INTERIM / "aguas_rs.png"
SAIDA_META = INTERIM / "aguas_rs_meta.json"

CATEGORIAS = ("permanente", "sazonal", "perdida", "efemera")

# Cores do overlay. NAO saem de theme/palette porque nao sao cor de dado
# tabular: sao um mapa tematico proprio, cuja gramatica e "agua de hoje x agua
# de antes". Azul para o que e agua; ocre para o que FOI agua — a inversao de
# temperatura e o que faz a leitura funcionar sem legenda.
CORES_RGBA: dict[str, tuple[int, int, int, int]] = {
    "permanente": (43, 143, 214, 235),
    "sazonal": (94, 190, 214, 205),
    "perdida": (193, 133, 58, 230),
    "efemera": (154, 108, 74, 195),
}
# Ordem de pintura: o que e agua hoje por cima do que foi. Um pixel que e
# permanente hoje e tambem foi sazonal antes deve se ler como rio, nao como
# passivo — senao o mapa acusa de "agua perdida" a margem de todo rio do estado.
ORDEM_PINTURA = ("efemera", "perdida", "sazonal", "permanente")

# Fracao minima da celula para pintar. Abaixo disso e ruido de classificacao
# de borda, e pintar tudo faria o estado inteiro parecer alagado.
LIMIAR_PINTURA = 0.03

# Curva de opacidade. A primeira versao usava alfa linear em `frac/0.6`, e o
# resultado era um mapa quase vazio: uma celula de 500 m atravessada por um rio
# de 60 m tem fracao ~0,12 e saia com 20% de opacidade — invisivel. Mas rio
# estreito nao e "pouca agua", e o objeto principal do mapa.
#
# A raiz comprime o topo e levanta a base, que e exatamente o que uma grade
# agregada precisa: o que importa e SE ha agua na celula, e so
# secundariamente quanta. O piso garante que nada pintado seja invisivel.
ALFA_ESCALA = 0.45
ALFA_PISO = 0.38


@dataclass(frozen=True)
class AguasResult:
    por_municipio: pd.DataFrame
    total_estado_km2: dict[str, float]
    meta: dict[str, Any]


def _carregar_grade() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if not GRADE_NPZ.exists():
        raise FileNotFoundError(
            f"{GRADE_NPZ} ausente — rode `python -m src.ingest.jrc_gsw`"
        )
    z = np.load(GRADE_NPZ, allow_pickle=True)
    meta = json.loads(z["meta"][0])
    counts = {c: z[f"count_{c}"] for c in CATEGORIAS}
    return counts, meta


def _transform(meta: dict[str, Any]):
    from rasterio.transform import from_origin

    b = meta["bbox"]
    return from_origin(b["lon_min"], b["lat_max"], meta["res_saida"], meta["res_saida"])


def _rasterizar_municipios(meta: dict[str, Any]) -> tuple[np.ndarray, list[int]]:
    """Grade de indices de municipio (0 = fora do RS), na mesma malha da grade.

    Indice e nao codigo IBGE porque o codigo (4300034...) nao cabe em int16 e
    um raster int32 de 1.620 x 1.360 por causa disso seria desperdicio.
    """
    from rasterio.features import rasterize

    if not MALHA_GEOJSON.exists():
        raise FileNotFoundError(
            f"{MALHA_GEOJSON} ausente — rode `python -m src.ingest.ibge_rs malha`"
        )
    geo = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    codigos: list[int] = []
    shapes = []
    for i, f in enumerate(geo["features"], start=1):
        codigos.append(int(f["properties"]["codarea"]))
        shapes.append((f["geometry"], i))

    grade = rasterize(
        shapes,
        out_shape=(meta["n_lat"], meta["n_lon"]),
        transform=_transform(meta),
        fill=0,
        dtype="int32",
        # all_touched=False: uma celula so pertence ao municipio que cobre seu
        # centro. Com True, celulas de fronteira entrariam em dois municipios e
        # a soma dos 497 passaria da area do estado.
        all_touched=False,
    )
    return grade, codigos


def _area_por_linha(meta: dict[str, Any]) -> np.ndarray:
    """Area de UM pixel nativo do JRC, por linha da grade, em km²."""
    b = meta["bbox"]
    lats = b["lat_max"] - (np.arange(meta["n_lat"]) + 0.5) * meta["res_saida"]
    m_lon = meta["res_nativa"] * 111_320.0 * np.cos(np.radians(lats))
    m_lat = meta["res_nativa"] * 110_540.0
    return (m_lon * m_lat / 1e6)[:, None]


def calcular() -> AguasResult:
    counts, meta = _carregar_grade()
    zonas, codigos = _rasterizar_municipios(meta)
    area_linha = _area_por_linha(meta)

    n = len(codigos)
    linhas: dict[str, np.ndarray] = {}
    for cat in CATEGORIAS:
        km2 = counts[cat] * area_linha
        # bincount sobre o raster de zonas: uma passada por categoria, sem
        # loop de 497 mascaras (que seria ~500x mais lento).
        soma = np.bincount(zonas.ravel(), weights=km2.ravel(), minlength=n + 1)
        linhas[cat] = soma[1:]  # descarta a zona 0 (fora do RS)

    df = pd.DataFrame({"cod_mun": codigos})
    for cat in CATEGORIAS:
        df[f"agua_{cat}_km2"] = np.round(linhas[cat], 3)

    # Area do municipio na mesma grade, para dar fracao e nao so valor absoluto:
    # 40 km² de agua perdida significam coisas opostas em Viamao e em Vanini.
    area_mun = np.bincount(
        zonas.ravel(),
        weights=np.broadcast_to(area_linha * (meta["fator"] ** 2), zonas.shape).ravel(),
        minlength=n + 1,
    )[1:]
    df["area_grade_km2"] = np.round(area_mun, 2)
    for cat in CATEGORIAS:
        df[f"frac_{cat}"] = np.where(area_mun > 0, linhas[cat] / area_mun, np.nan).round(6)

    total = {c: round(float(linhas[c].sum()), 1) for c in CATEGORIAS}
    meta_out = {
        "produto": "JRC Global Surface Water v1.4 (transitions)",
        "janela": "1984-2021",
        "nao_cobre": "cheia de maio de 2024 — a serie termina em 2021",
        "resolucao_nativa_m": 30,
        "recorte": "malha municipal IBGE — oceano e estados vizinhos excluidos",
        "area_estado_km2": round(float(area_mun.sum()), 1),
        "total_km2": total,
        "referencia": (
            "Pekel, J.-F. et al. High-resolution mapping of global surface water "
            "and its long-term changes. Nature 540, 418-422 (2016)."
        ),
    }
    return AguasResult(por_municipio=df, total_estado_km2=total, meta=meta_out)


def gerar_overlay() -> dict[str, Any]:
    """PNG RGBA das categorias, recortado no RS, para sobrepor no mapa.

    PNG e nao vetor: sao ~2 milhoes de celulas: como SVG viraria dezenas de MB
    de <path> e travaria o navegador. Como imagem alinhada ao bbox, sao
    algumas centenas de KB e o alinhamento e exato, porque a projecao do mapa
    e linear em lon/lat.
    """
    from PIL import Image

    counts, meta = _carregar_grade()
    zonas, _ = _rasterizar_municipios(meta)
    dentro = zonas > 0

    n_px = meta["fator"] ** 2
    rgba = np.zeros((meta["n_lat"], meta["n_lon"], 4), dtype=np.uint8)

    for cat in ORDEM_PINTURA:
        frac = counts[cat] / n_px
        mask = dentro & (frac >= LIMIAR_PINTURA)
        if not mask.any():
            continue
        r, g, b, a_max = CORES_RGBA[cat]
        # Alfa cresce com a raiz da fracao ocupada, com piso — ver ALFA_ESCALA:
        # um lago que cobre a celula inteira ainda pinta mais forte que um rio
        # estreito, mas o rio continua legivel.
        alfa = np.clip(np.sqrt(frac / ALFA_ESCALA), ALFA_PISO, 1.0) * a_max
        rgba[..., 0][mask] = r
        rgba[..., 1][mask] = g
        rgba[..., 2][mask] = b
        rgba[..., 3][mask] = alfa[mask].astype(np.uint8)

    Image.fromarray(rgba, mode="RGBA").save(SAIDA_PNG, optimize=True)

    b = meta["bbox"]
    info = {
        "png": SAIDA_PNG.name,
        "bbox": b,
        "n_lon": meta["n_lon"],
        "n_lat": meta["n_lat"],
        "limiar_pintura": LIMIAR_PINTURA,
        "ordem_pintura": list(ORDEM_PINTURA),
        "cores": {k: list(v) for k, v in CORES_RGBA.items()},
    }
    SAIDA_META.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    return info


def run() -> AguasResult:
    res = calcular()
    res.por_municipio.to_parquet(SAIDA_PARQUET, index=False)
    info = gerar_overlay()
    meta = {**res.meta, "overlay": info}
    (INTERIM / "aguas_rs_resumo.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return AguasResult(res.por_municipio, res.total_estado_km2, meta)


def load() -> pd.DataFrame | None:
    """Tabela por municipio, ou None se ainda nao calculada."""
    if not SAIDA_PARQUET.exists():
        return None
    return pd.read_parquet(SAIDA_PARQUET)


def load_meta() -> dict[str, Any] | None:
    path = INTERIM / "aguas_rs_resumo.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    r = run()
    print(f"[OK] aguas — area do estado na grade: {r.meta['area_estado_km2']:,.0f} km²")
    for k, v in r.total_estado_km2.items():
        pct = 100 * v / r.meta["area_estado_km2"]
        print(f"     {k:12s} {v:>9.1f} km²  ({pct:4.1f}% do estado)")
