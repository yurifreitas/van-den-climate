"""GHSL Built-up Surface — quanto de cada municipio e superficie construida.

A pergunta que esta fonte responde
==================================

"Onde a chuva cai sobre concreto em vez de solo?" Essa e a variavel que separa
alagamento de inundacao, e ate agora a central nao a tinha: a estrategia de
drenagem urbana em `src/risk/contencao.py` ja existia com o gatilho pronto, e
disparava em ZERO municipios porque ninguem alimentava `frac_construida`.

O Global Human Settlement Layer (Joint Research Centre, Comissao Europeia,
release R2023A) mede **metros quadrados de superficie construida por celula**,
derivados de Sentinel-2 e Landsat. O produto usado aqui e o
`GHS_BUILT_S_E2025_GLOBE_R2023A_4326_30ss_V1_0`: epoca 2025, grade global em
graus, celula de 30 segundos de arco (~0,86 km no Equador).

Por que a epoca 2025 e nao 2020: a impermeabilizacao que importa para a cheia
de amanha e a de hoje. E por que 30ss e nao 100 m: a agregacao aqui e por
municipio inteiro, e a celula de 1 km ja da entre 300 e 30.000 celulas por
municipio do RS — resolucao de sobra para uma fracao municipal, com 130 MB em
vez de 12 GB.

O QUE A FRACAO SIGNIFICA, E O QUE ELA NAO SIGNIFICA
===================================================

`frac_construida` = (m2 construidos no municipio) / (area do municipio).

Ela e **proxy de impermeabilizacao, nao medida dela**. Superficie construida
no GHSL e telhado e pavimento detectados por satelite; nao distingue asfalto
de piso drenante, nao ve calcada permeavel, e nao ve compactacao de solo
agricola — que impermeabiliza sem construir nada. Um municipio rural com solo
compactado por pecuaria pode escoar como cidade e aparecer aqui com 1%.

A leitura correta e comparativa e ordinal: entre dois municipios do RS, o de
fracao maior tem mais area onde a chuva nao infiltra. Nao e um coeficiente de
escoamento, e nao entra em nenhuma conta de vazao.

CELULA NAO TEM AREA CONSTANTE
=============================

A grade e em GRAUS, nao em metros. Uma celula de 30" perto de Chui (-33,7)
cobre ~17% menos area que uma perto de Barra do Quarai (-30,2), porque o
meridiano converge. Somar celulas como se fossem iguais inflaria a fracao no
norte do estado e a deflacionaria no sul — um gradiente falso norte-sul
exatamente na direcao em que o estado varia de verdade.

Por isso a area de cada celula e calculada por linha, com o cosseno da
latitude do centro da celula. E por isso o denominador e a soma das areas de
celula do municipio, e nao a area oficial do IBGE: assim numerador e
denominador vivem na mesma grade, e o erro de rasterizacao (celula de borda
contada inteira) se cancela em vez de se somar.
"""
from __future__ import annotations

import json
import math
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

ZIP_PATH = DATA_RAW / "ghsl_built" / "ghsl_built_2025.zip"
TIF_NO_ZIP = "GHS_BUILT_S_E2025_GLOBE_R2023A_4326_30ss_V1_0.tif"
MALHA_GEOJSON = DATA_INTERIM / "ibge_malha_rs.geojson"
SAIDA = DATA_INTERIM / "ghsl_built_rs.parquet"

INGESTOR_VERSION = "1"
EPOCA = 2025
FONTE = (
    "GHS-BUILT-S R2023A, epoca 2025, 30 arcsec — Joint Research Centre, "
    "Comissao Europeia. Pesaresi & Politis (2023). Dados sob CC BY 4.0."
)

# Caixa do RS com folga de meio grau: a rasterizacao precisa das celulas de
# borda inteiras, e recortar rente perde o municipio da ponta.
BBOX = {"lon_min": -58.2, "lon_max": -49.1, "lat_min": -34.3, "lat_max": -26.5}

R_TERRA_M = 6_371_000.0


@dataclass(frozen=True)
class Resultado:
    df: pd.DataFrame
    meta: dict[str, Any]


def _area_celula_m2(lat_centro: np.ndarray, res_graus: float) -> np.ndarray:
    """Area de uma celula de `res_graus` x `res_graus` centrada em cada latitude.

    Formula exata da area de um quadrilatero esferico, nao a aproximacao
    `cos(lat)`: na altura do RS as duas diferem pouco, mas a exata custa o
    mesmo e nao tem regime onde erre.
    """
    dlat = math.radians(res_graus)
    dlon = math.radians(res_graus)
    lat_r = np.radians(lat_centro)
    return (R_TERRA_M**2) * dlon * (np.sin(lat_r + dlat / 2) - np.sin(lat_r - dlat / 2))


def build() -> Resultado:
    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"{ZIP_PATH} ausente — baixe o pacote GHS-BUILT-S 30ss de "
            "https://human-settlement.emergency.copernicus.eu/download.php"
        )
    if not MALHA_GEOJSON.exists():
        raise FileNotFoundError(
            f"{MALHA_GEOJSON} ausente — rode `python -m src.ingest.ibge_rs`"
        )

    import rasterio
    from rasterio.features import rasterize
    from rasterio.windows import from_bounds

    with zipfile.ZipFile(ZIP_PATH) as z:
        nomes = [n for n in z.namelist() if n.endswith(".tif")]
    if TIF_NO_ZIP not in nomes:
        raise FileNotFoundError(f"{TIF_NO_ZIP} nao esta no zip; ha {nomes}")

    # /vsizip le o GeoTIFF de 130 MB direto de dentro do zip: nao ha copia
    # descompactada de 130 MB no disco para manter em sincronia com o bruto.
    vsi = f"/vsizip/{ZIP_PATH.as_posix()}/{TIF_NO_ZIP}"
    with rasterio.open(vsi) as src:
        janela = from_bounds(
            BBOX["lon_min"], BBOX["lat_min"], BBOX["lon_max"], BBOX["lat_max"],
            transform=src.transform,
        ).round_offsets().round_lengths()
        built = src.read(1, window=janela).astype("float64")
        transform = src.window_transform(janela)
        nodata = src.nodata
        res_graus = abs(src.transform.a)

    # Fora d'agua o produto traz nodata; virar zero aqui e correto — oceano
    # nao e area construida — mas so depois do recorte por municipio, que ja
    # exclui o mar. Antes disso, nodata somaria lixo no denominador.
    if nodata is not None:
        built[built == nodata] = 0.0
    built[built < 0] = 0.0

    malha = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    feats = malha["features"]
    codigos = [int(f["properties"]["codarea"]) for f in feats]
    # A malha do IBGE traz so `codarea` — o nome vem do MUNIC, como nas
    # outras camadas. Sem isto a saida sai com 497 nomes None.
    munic = pd.read_parquet(DATA_INTERIM / "ibge_munic_rs.parquet")[["cod_mun", "municipio"]]
    nome_por_cod = {int(r.cod_mun): r.municipio for r in munic.itertuples()}
    nomes_mun = [nome_por_cod.get(c) for c in codigos]

    # Uma rasterizacao so, com o INDICE do municipio como valor da celula.
    # 497 rasterizacoes separadas dariam o mesmo resultado e custariam 497x.
    # Indice comeca em 1 porque 0 e o fundo.
    rotulos = rasterize(
        ((f["geometry"], i + 1) for i, f in enumerate(feats)),
        out_shape=built.shape,
        transform=transform,
        fill=0,
        dtype="int32",
    )

    n_lin, n_col = built.shape
    lat_topo = transform.f
    lat_centros = lat_topo - (np.arange(n_lin) + 0.5) * res_graus
    area_lin = _area_celula_m2(lat_centros, res_graus)          # (n_lin,)
    area = np.repeat(area_lin[:, None], n_col, axis=1)          # (n_lin, n_col)

    plano = rotulos.ravel()
    n = len(feats) + 1
    m2_construidos = np.bincount(plano, weights=built.ravel(), minlength=n)
    m2_celulas = np.bincount(plano, weights=area.ravel(), minlength=n)
    n_celulas = np.bincount(plano, minlength=n)

    linhas = []
    for i, cod in enumerate(codigos, start=1):
        area_grade = float(m2_celulas[i])
        constr = float(m2_construidos[i])
        # Municipio pequeno demais para a grade de 1 km sai com fracao None,
        # nunca 0.0: zero aqui leria como "medimos e nao ha nada construido".
        frac = round(constr / area_grade, 5) if area_grade > 0 and n_celulas[i] >= 3 else None
        linhas.append({
            "cod_mun": cod,
            "municipio": nomes_mun[i - 1],
            "frac_construida": frac,
            "km2_construidos": round(constr / 1e6, 3),
            "km2_grade": round(area_grade / 1e6, 3),
            "n_celulas": int(n_celulas[i]),
            "epoca": EPOCA,
            "basis": "measured" if frac is not None else None,
        })

    df = pd.DataFrame(linhas).sort_values("cod_mun").reset_index(drop=True)

    cobertos = df[df.frac_construida.notna()]
    meta = {
        "version": INGESTOR_VERSION,
        "fonte": FONTE,
        "epoca": EPOCA,
        "res_graus": res_graus,
        "n_municipios": len(df),
        "n_com_fracao": int(len(cobertos)),
        "km2_construidos_rs": round(float(cobertos.km2_construidos.sum()), 1),
        "km2_grade_rs": round(float(cobertos.km2_grade.sum()), 1),
        "limites": [
            "Superficie construida e PROXY de impermeabilizacao, nao medida dela: "
            "nao distingue asfalto de piso drenante e nao ve compactacao de solo "
            "agricola, que impermeabiliza sem construir.",
            "Leitura valida e ordinal e comparativa entre municipios. Nao e "
            "coeficiente de escoamento e nao entra em conta de vazao.",
            "Celula de ~1 km: municipio com menos de 3 celulas sai sem fracao, "
            "nunca com zero.",
            "Area de celula calculada por latitude. Somar celulas como iguais "
            "criaria um gradiente falso norte-sul de ate 17% no estado.",
        ],
    }
    return Resultado(df=df, meta=meta)


def main() -> int:
    r = build()
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    r.df.to_parquet(SAIDA, index=False)
    (DATA_INTERIM / "ghsl_built_rs.meta.json").write_text(
        json.dumps(r.meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    top = r.df.dropna(subset=["frac_construida"]).nlargest(8, "frac_construida")
    print(f"[OK] {len(r.df)} municipios -> {SAIDA}")
    print(f"     {r.meta['km2_construidos_rs']} km2 construidos em "
          f"{r.meta['km2_grade_rs']} km2 de grade")
    for _, m in top.iterrows():
        print(f"     {m.frac_construida * 100:6.2f}%  {m.municipio}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
