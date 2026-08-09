"""Copernicus DEM — a declividade real, no lugar do adjetivo.

O QUE ESTA FONTE CORRIGE
========================

Ate aqui o relevo entrava na central por uma CLASSE QUALITATIVA da carta
pedologica do IBGE: "plano", "suave ondulado", "ondulado", "forte ondulado",
"montanhoso". A camada de degradacao traduzia cada rotulo num fator LS de
tabela, e a camada hidrologica usava o mesmo rotulo para ordenar a velocidade
de resposta.

O problema nao e o rotulo ser grosseiro — e o LS crescer QUARENTA VEZES do
plano ao montanhoso. Num fator com essa alavanca, a diferenca entre "ondulado"
e "forte ondulado" domina o resultado inteiro, e essa diferenca estava sendo
decidida por um adjetivo escrito numa carta de 1:250.000, que descreve o
poligono inteiro por sua feicao predominante.

O Copernicus DEM (ESA, derivado do TanDEM-X) da a altitude medida. Dela sai a
declividade celula a celula, e dela sai um LS que varia DENTRO do municipio em
vez de herdar um rotulo.

POR QUE 90 m, E NAO 30 m
========================

O produto GLO-30 existe e e aberto, mas o estado inteiro sairia perto de 3 GB
contra 420 MB do GLO-90. A pergunta aqui e a distribuicao de declividade por
municipio — quantos por cento da area estao acima de 20% de inclinacao — e para
isso 90 m e suficiente: a encosta que importa tem centenas de metros de
extensao, nao noventa.

O que se perde e real e precisa ser dito: a 90 m, o talude de corte de estrada,
a barranca de arroio e o degrau de terraco desaparecem. A declividade daqui e a
da ENCOSTA, nao a do talude.

TRES CUIDADOS QUE A GRADE EM GRAUS IMPOE
========================================

1. **Espacamento metrico varia com a latitude.** Uma celula de 3 segundos de
   arco tem ~92 m no eixo norte-sul em qualquer lugar, mas no eixo leste-oeste
   tem 80 m em Chui e 84 m em Barra do Quarai. Calcular declividade com
   espacamento fixo inclinaria o estado inteiro numa direcao.

2. **O DEM e de SUPERFICIE, nao de terreno.** TanDEM-X mede o topo do dossel e
   do telhado. Em area florestada a declividade sai contaminada pela borda da
   mata; em area urbana densa, pelos predios. Nao ha correcao aplicada aqui —
   ha declaracao.

3. **Borda de tile.** A declividade e calculada por diferenca finita dentro de
   cada tile, entao a primeira e a ultima linha de cada um usam vizinho
   replicado. Sao 72 tiles e o efeito e desprezivel na media municipal, mas
   existe.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

SOURCE_ID = "copernicus_dem"
INGESTOR_VERSION = "1"
BASE_URL = "https://copernicus-dem-90m.s3.amazonaws.com"

MALHA_GEOJSON = DATA_INTERIM / "ibge_malha_rs.geojson"
MUNIC_PARQUET = DATA_INTERIM / "ibge_munic_rs.parquet"
SAIDA = DATA_INTERIM / "copernicus_dem_rs.parquet"
META_SAIDA = DATA_INTERIM / "copernicus_dem_rs.meta.json"

# Tiles de 1 grau, nomeados pelo canto SUDOESTE.
LAT_MIN, LAT_MAX = -34, -27
LON_MIN, LON_MAX = -58, -50

# Classes de declividade em porcentagem, nas mesmas faixas que o IBGE usa para
# nomear relevo. Manter as faixas iguais e o que permite comparar o adjetivo da
# carta com a medida — e mostrar onde os dois discordam.
CLASSES_DECLIVIDADE = (
    ("plano", 0.0, 3.0),
    ("suave_ondulado", 3.0, 8.0),
    ("ondulado", 8.0, 20.0),
    ("forte_ondulado", 20.0, 45.0),
    ("montanhoso", 45.0, 75.0),
    ("escarpado", 75.0, float("inf")),
)

# Comprimento de rampa assumido no fator L, em metros. E o mesmo valor que a
# camada de degradacao ja assumia com a classe qualitativa — mantido igual de
# proposito, para que a mudanca de resultado venha da declividade medida e nao
# de dois parametros trocados ao mesmo tempo.
RAMPA_M = 50.0


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


@dataclass(frozen=True)
class Resultado:
    df: pd.DataFrame
    meta: dict[str, Any]


def _nome_tile(lat: int, lon: int) -> str:
    ns = f"S{abs(lat):02d}" if lat < 0 else f"N{lat:02d}"
    ew = f"W{abs(lon):03d}" if lon < 0 else f"E{lon:03d}"
    return f"Copernicus_DSM_COG_30_{ns}_00_{ew}_00_DEM"


def _baixar_tile(lat: int, lon: int, destino: Path) -> Path | None:
    """Baixa um tile, ou devolve None se ele nao existe.

    Tile ausente e resposta NORMAL, nao erro: o produto so publica onde ha
    terra, e boa parte da caixa do RS e oceano ou Uruguai/Argentina sem
    cobertura no recorte. Tratar 404 como falha faria a ingestao inteira
    depender do formato do litoral.
    """
    nome = _nome_tile(lat, lon)
    arq = destino / f"{nome}.tif"
    if arq.exists():
        return arq
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    url = f"{BASE_URL}/{nome}/{nome}.tif"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
        with urllib.request.urlopen(req, timeout=600) as r:
            dados = r.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise IngestError(f"{SOURCE_ID}: falha em {url}: {exc}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise IngestError(f"{SOURCE_ID}: falha em {url}: {exc}") from exc
    destino.mkdir(parents=True, exist_ok=True)
    arq.write_bytes(dados)
    (destino / f"provenance.{nome}.json").write_text(
        json.dumps(
            {
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(dados).hexdigest(),
                "product_version": "Copernicus DEM GLO-90 (ESA, TanDEM-X)",
                "ingestor_version": INGESTOR_VERSION,
                "bytes": len(dados),
                "notes": "Modelo de SUPERFICIE: mede topo de dossel e telhado, nao o terreno.",
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return arq


def _raw_dir() -> Path:
    base = DATA_RAW / SOURCE_ID
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True) if base.exists() else []
    # Um diretorio so: o DEM nao muda entre execucoes (produto estatico de
    # 2019), e versionar por timestamp aqui geraria 420 MB por rodada.
    return dirs[0] if dirs else base / "glo90"


def _declividade_pct(z: np.ndarray, lat_centros: np.ndarray, res_graus: float) -> np.ndarray:
    """Declividade em porcentagem, com espacamento metrico por linha."""
    dy = res_graus * 110_540.0
    dx = res_graus * 111_320.0 * np.cos(np.radians(lat_centros))
    gz_y, gz_x = np.gradient(z, edge_order=1)
    # `np.gradient` devolve variacao por CELULA; dividir pelo espacamento em
    # metros converte para tangente. O eixo x usa dx da propria linha.
    tan_y = gz_y / dy
    tan_x = gz_x / dx[:, None]
    return 100.0 * np.sqrt(tan_x**2 + tan_y**2)


def fator_ls(decliv_pct: np.ndarray, rampa_m: float = RAMPA_M) -> np.ndarray:
    """LS da RUSLE a partir da declividade medida.

    S segue McCool, com quebra em 9% de inclinacao; m do fator L vem da razao
    entre erosao em sulco e entre sulcos. Sao as formulas do manual, nao um
    ajuste nosso — o que e nosso, e esta declarado, e o comprimento de rampa.
    """
    theta = np.arctan(decliv_pct / 100.0)
    sin_t = np.sin(theta)
    s = np.where(decliv_pct < 9.0, 10.8 * sin_t + 0.03, 16.8 * sin_t - 0.50)
    s = np.maximum(s, 0.0)
    beta = (sin_t / 0.0896) / (3.0 * np.power(np.maximum(sin_t, 1e-6), 0.8) + 0.56)
    m = beta / (1.0 + beta)
    l = np.power(rampa_m / 22.13, m)
    return l * s


def build() -> Resultado:
    if not MALHA_GEOJSON.exists():
        raise FileNotFoundError(f"{MALHA_GEOJSON} ausente — rode `python -m src.ingest.ibge_rs`")

    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    malha = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    feats = malha["features"]
    codigos = [int(f["properties"]["codarea"]) for f in feats]
    munic = pd.read_parquet(MUNIC_PARQUET)[["cod_mun", "municipio"]]
    nomes = {int(r.cod_mun): r.municipio for r in munic.itertuples()}

    # Caixa de cada municipio, para so rasterizar o que toca o tile.
    caixas = []
    for f in feats:
        g = f["geometry"]
        aneis = g["coordinates"] if g["type"] == "Polygon" else [
            a for poly in g["coordinates"] for a in poly
        ]
        xs = [p[0] for anel in aneis for p in anel]
        ys = [p[1] for anel in aneis for p in anel]
        caixas.append((min(xs), min(ys), max(xs), max(ys)))

    n = len(feats) + 1
    soma_z = np.zeros(n)
    soma_s = np.zeros(n)
    soma_ls = np.zeros(n)
    contagem = np.zeros(n)
    por_classe = {nome: np.zeros(n) for nome, _, _ in CLASSES_DECLIVIDADE}
    amostras: dict[int, list[np.ndarray]] = {}

    destino = _raw_dir()
    tiles_lidos, tiles_ausentes = 0, 0

    for lat in range(LAT_MIN, LAT_MAX + 1):
        for lon in range(LON_MIN, LON_MAX + 1):
            arq = _baixar_tile(lat, lon, destino)
            if arq is None:
                tiles_ausentes += 1
                continue
            with rasterio.open(arq) as src:
                z = src.read(1).astype("float32")
                nodata = src.nodata
                t = src.transform
                res = abs(t.a)
                n_lin, n_col = z.shape
                lat_centros = t.f - (np.arange(n_lin) + 0.5) * res
                transform = from_origin(t.c, t.f, res, res)

            if nodata is not None:
                z[z == nodata] = np.nan
            # Oceano vem como zero exato em grande extensao; declividade ali e
            # ruido e entraria como area plana enorme no municipio litoraneo.
            z[z <= -100] = np.nan

            selecao = [
                (feats[i]["geometry"], i + 1)
                for i in range(len(feats))
                if not (caixas[i][2] < lon or caixas[i][0] > lon + 1
                        or caixas[i][3] < lat or caixas[i][1] > lat + 1)
            ]
            if not selecao:
                continue
            rot = rasterize(selecao, out_shape=z.shape, transform=transform,
                            fill=0, dtype="int32")
            if not rot.any():
                continue

            decliv = _declividade_pct(np.nan_to_num(z, nan=0.0), lat_centros, res)
            ls = fator_ls(decliv)
            valido = (rot > 0) & np.isfinite(z)

            chave = rot[valido]
            soma_z += np.bincount(chave, weights=z[valido], minlength=n)
            soma_s += np.bincount(chave, weights=decliv[valido], minlength=n)
            soma_ls += np.bincount(chave, weights=ls[valido], minlength=n)
            contagem += np.bincount(chave, minlength=n)
            d = decliv[valido]
            for nome, lo, hi in CLASSES_DECLIVIDADE:
                por_classe[nome] += np.bincount(chave[(d >= lo) & (d < hi)], minlength=n)
            # Amostra para percentis: guardar toda a distribuicao custaria
            # gigabytes; 1 a cada 50 celulas preserva o percentil 90 com folga.
            for cod_idx, dd in zip(chave[::50], d[::50]):
                amostras.setdefault(int(cod_idx), []).append(dd)
            tiles_lidos += 1

    linhas = []
    for i, cod in enumerate(codigos, start=1):
        if contagem[i] < 10:
            continue
        amostra = np.array(amostras.get(i, []), dtype="float32")
        linhas.append({
            "cod_mun": cod,
            "municipio": nomes.get(cod),
            "n_celulas": int(contagem[i]),
            "altitude_media_m": round(float(soma_z[i] / contagem[i]), 1),
            "declividade_media_pct": round(float(soma_s[i] / contagem[i]), 2),
            "declividade_p90_pct": (
                round(float(np.percentile(amostra, 90)), 2) if amostra.size >= 20 else None
            ),
            "ls_medio": round(float(soma_ls[i] / contagem[i]), 3),
            **{
                f"frac_{nome}": round(float(por_classe[nome][i] / contagem[i]), 4)
                for nome, _, _ in CLASSES_DECLIVIDADE
            },
        })

    df = pd.DataFrame(linhas).sort_values("cod_mun").reset_index(drop=True)
    meta = {
        "version": INGESTOR_VERSION,
        "fonte": "Copernicus DEM GLO-90 (ESA, derivado do TanDEM-X), via AWS Open Data",
        "resolucao": "3 arcsec (~90 m)",
        "tiles_lidos": tiles_lidos,
        "tiles_ausentes": tiles_ausentes,
        "n_municipios": len(df),
        "rampa_assumida_m": RAMPA_M,
        "declividade_media_rs_pct": round(float(df.declividade_media_pct.mean()), 2),
        "limites": [
            "E modelo de SUPERFICIE, nao de terreno: mede topo de dossel e telhado. "
            "Em area florestada a declividade sai contaminada pela borda da mata.",
            "A 90 m, talude de corte de estrada, barranca de arroio e degrau de "
            "terraco desaparecem. E a declividade da ENCOSTA, nao a do talude.",
            "Declividade por diferenca finita dentro de cada tile: a primeira e a "
            "ultima linha usam vizinho replicado.",
            "O comprimento de rampa do fator L (50 m) continua sendo suposicao "
            "nossa — o DEM corrige a declividade, nao o comprimento.",
        ],
    }
    return Resultado(df=df, meta=meta)


def main() -> int:
    r = build()
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    r.df.to_parquet(SAIDA, index=False)
    META_SAIDA.write_text(json.dumps(r.meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {SOURCE_ID}: {len(r.df)} municipios, {r.meta['tiles_lidos']} tiles "
          f"({r.meta['tiles_ausentes']} ausentes) -> {SAIDA.name}")
    print(f"     declividade media do estado: {r.meta['declividade_media_rs_pct']}%")
    topo = r.df.nlargest(6, "declividade_media_pct")
    for _, m in topo.iterrows():
        print(f"     {m.declividade_media_pct:5.1f}%  LS {m.ls_medio:5.2f}  {m.municipio}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
