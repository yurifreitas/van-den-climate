"""JRC Global Surface Water — onde havia agua, onde ha, e onde a agua voltou.

A pergunta que esta fonte responde
==================================

"Que areas ja foram agua e voltaram a encher?" Nenhuma base climatica responde
isso. Esta responde, e com medicao direta: o Joint Research Centre da Comissao
Europeia classificou cada pixel de 30 m do planeta a partir de ~4 milhoes de
cenas Landsat entre 1984 e 2021 (Pekel et al., Nature 2016), e o produto
`transitions` diz, para cada pixel, o que ACONTECEU com a agua ali ao longo
dessas quatro decadas.

As classes que importam para uma central de risco de cheia:

    1  agua permanente        -> rio e lago de hoje
    4  agua sazonal           -> varzea, banhado, area que enche todo ano
    3  agua PERMANENTE PERDIDA-> leito ou lago que secou ou foi drenado
    6  agua SAZONAL PERDIDA   -> banhado suprimido
    2  nova permanente        -> barragem, acude, meandro capturado
    5  nova sazonal
    7  sazonal -> permanente
    8  permanente -> sazonal
    9  efemera permanente     -> encheu uma vez e sumiu
    10 efemera sazonal

`3`, `6`, `9` e `10` sao o achado central: sao o registro de que aquele
terreno JA FOI agua. Terreno que ja foi agua nao virou terreno seco por
mudanca de fisica — virou por drenagem, aterro, estiagem ou obra. A agua sabe
o caminho de volta, e em 2024 ela o fez.

LIMITE QUE PRECISA VIR JUNTO DE TODO NUMERO DESTA FONTE
=======================================================

A serie do JRC termina em **2021**. Ela NAO contem a cheia de maio de 2024.
Isso nao e um defeito para o nosso uso — e o que torna o cruzamento honesto:
a camada e um retrato do que ja era planicie de agua ANTES do evento, feito
sem nenhum conhecimento dele. Quando um municipio com muita "agua perdida"
aparece tambem com inundacao declarada em 2024, isso e coincidencia entre
duas bases independentes, nao circularidade.

O que ela tambem nao ve: curso d'agua mais estreito que ~30 m, agua sob
dossel florestal, e a distincao entre lago natural e acude. E um sensor
optico de resolucao media, nao um levantamento hidrografico.

E os "lagos de mais de 150 anos"?
=================================

Nao existem como dado. A serie de satelite comeca em 1984 — 42 anos, nao 150.
Nao ha base publica vetorial da hidrografia do RS do seculo XIX; o que existe
sao cartas historicas em acervo (imagem, nao geometria). Este modulo NAO
finge cobrir 150 anos: cobre 1984-2021 e diz isso em cada payload. A janela
mais longa vem da geologia quaternaria (paleocanais), em modulo separado.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

SOURCE_ID = "jrc_gsw"
INGESTOR_VERSION = "1"
BASE_URL = "https://storage.googleapis.com/global-surface-water/downloads2021/transitions"
TILE_FMT = "transitions_{lon}_{lat}v1_4_2021.tif"

# Tiles de 10x10 graus nomeados pelo canto SUPERIOR-ESQUERDO. O RS ocupa
# lon [-57.6, -49.7] e lat [-27.1, -33.8], entao cruza tanto o meridiano -50
# quanto o paralelo -30: quatro tiles, nao um.
TILES = [("60W", "20S"), ("50W", "20S"), ("60W", "30S"), ("50W", "30S")]

# Recorte do RS com folga de meio grau — a malha do IBGE define a fronteira
# real; aqui so precisamos garantir que nada do estado fique de fora.
RS_BBOX = {"lon_min": -57.70, "lon_max": -49.60, "lat_min": -33.80, "lat_max": -27.00}

RES_NATIVA = 0.00025          # graus/pixel do JRC (~27 m em latitude)
RES_SAIDA = 0.005             # graus/celula da grade agregada (~550 m)
FATOR = int(round(RES_SAIDA / RES_NATIVA))  # 20 pixels nativos por lado

# Classes agregadas. Reduzir 11 classes do JRC a 5 categorias e uma escolha
# editorial: o mapa precisa ser lido, nao decifrado. As 11 originais seguem
# recuperaveis do bruto em disco.
CATEGORIAS: dict[str, tuple[int, ...]] = {
    "permanente": (1, 2, 7),      # e agua hoje, o ano inteiro
    "sazonal": (4, 5, 8),         # e agua parte do ano — varzea e banhado
    "perdida": (3, 6),            # ERA agua e deixou de ser
    "efemera": (9, 10),           # encheu e sumiu dentro da serie
}
CLASSES_JRC = 11


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


@dataclass(frozen=True)
class Grade:
    """Grade agregada de contagens por categoria.

    `counts[cat]` guarda o numero de PIXELS NATIVOS de cada categoria dentro
    da celula — nao a fracao. Contagem e aditiva entre tiles e converte para
    area sem perda; fracao nao sobrevive a juncao de tiles.
    """

    counts: dict[str, np.ndarray]
    lon_min: float
    lat_max: float
    n_lon: int
    n_lat: int

    @property
    def bbox(self) -> dict[str, float]:
        return {
            "lon_min": self.lon_min,
            "lon_max": self.lon_min + self.n_lon * RES_SAIDA,
            "lat_max": self.lat_max,
            "lat_min": self.lat_max - self.n_lat * RES_SAIDA,
        }


def _http_get(url: str, dest: Path) -> None:
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp, dest.open("wb") as fh:
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        dest.unlink(missing_ok=True)
        raise IngestError(f"{SOURCE_ID}: falha na etapa fetch, url={url}: {exc}") from exc


def _latest_raw_dir() -> Path | None:
    base = DATA_RAW / SOURCE_ID
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def baixar_tiles() -> Path:
    """Garante os 4 tiles em disco e devolve o diretorio bruto.

    Cache agressivo por design: sao ~130 MB de um produto que so muda quando o
    JRC publica versao nova (v1.4 de 2021 e a corrente). Rebaixar isso a cada
    execucao seria desperdicio de banda e de paciencia.
    """
    latest = _latest_raw_dir()
    if latest is not None and all((latest / TILE_FMT.format(lon=lo, lat=la)).exists() for lo, la in TILES):
        return latest
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: modo offline sem download previo em {DATA_RAW / SOURCE_ID}")

    out_dir = DATA_RAW / SOURCE_ID / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for lon, lat in TILES:
        nome = TILE_FMT.format(lon=lon, lat=lat)
        dest = out_dir / nome
        print(f"  baixando {nome} ...", flush=True)
        _http_get(f"{BASE_URL}/{nome}", dest)
        hashes[nome] = hashlib.sha256(dest.read_bytes()).hexdigest()

    # `sha256` e UM digest, sempre — o contrato de /health/sources promete uma
    # string e um dicionario ali quebraria o endpoint inteiro por causa de uma
    # fonte. Como esta fonte tem 4 arquivos, o digest publicado e o hash da
    # lista ordenada de hashes: muda se qualquer tile mudar, e continua sendo
    # um valor unico comparavel entre execucoes. Os hashes por arquivo ficam
    # ao lado, para auditoria.
    combinado = hashlib.sha256(
        "".join(f"{k}:{hashes[k]}" for k in sorted(hashes)).encode()
    ).hexdigest()

    (out_dir / "provenance.json").write_text(
        json.dumps(
            {
                "url": BASE_URL,
                "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
                "sha256": combinado,
                "sha256_por_arquivo": hashes,
                "product_version": "GSW v1.4 (1984-2021)",
                "ingestor_version": INGESTOR_VERSION,
                "rows": len(TILES),
                "notes": (
                    "JRC Global Surface Water, camada 'transitions'. Pekel et al., Nature 2016. "
                    "Serie termina em 2021 — NAO contem a cheia de maio de 2024."
                ),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out_dir


def agregar(raw_dir: Path) -> Grade:
    """Le os 4 tiles em blocos e acumula contagens por categoria na grade.

    Le em blocos de linhas em vez de tudo de uma vez: o recorte do RS em
    resolucao nativa tem ~31.600 x 27.200 pixels (860 milhoes). Carregar isso
    inteiro custaria ~860 MB de RAM para produzir uma grade de 1.620 x 1.360 —
    trabalho e memoria desproporcionais ao resultado.
    """
    import rasterio
    from rasterio.windows import Window

    n_lon = int(round((RS_BBOX["lon_max"] - RS_BBOX["lon_min"]) / RES_SAIDA))
    n_lat = int(round((RS_BBOX["lat_max"] - RS_BBOX["lat_min"]) / RES_SAIDA))
    counts = {cat: np.zeros((n_lat, n_lon), dtype=np.int32) for cat in CATEGORIAS}

    for lon_t, lat_t in TILES:
        caminho = raw_dir / TILE_FMT.format(lon=lon_t, lat=lat_t)
        if not caminho.exists():
            raise IngestError(f"{SOURCE_ID}: tile ausente: {caminho}")

        with rasterio.open(caminho) as src:
            t = src.transform
            # Interseccao do tile com o recorte do RS, em pixel do tile.
            col0 = max(0, int(np.floor((RS_BBOX["lon_min"] - t.c) / t.a)))
            col1 = min(src.width, int(np.ceil((RS_BBOX["lon_max"] - t.c) / t.a)))
            row0 = max(0, int(np.floor((RS_BBOX["lat_max"] - t.f) / t.e)))
            row1 = min(src.height, int(np.ceil((RS_BBOX["lat_min"] - t.f) / t.e)))
            if col1 <= col0 or row1 <= row0:
                continue  # tile nao toca o RS

            # Alinha o inicio a um multiplo de FATOR para que cada celula de
            # saida receba exatamente FATOR x FATOR pixels nativos. Sem isso as
            # celulas de borda misturariam contagens de duas linhas da grade.
            col0 -= (col0 - 0) % FATOR
            row0 -= (row0 - 0) % FATOR

            bloco = FATOR * 100  # ~2000 linhas nativas por leitura
            for r in range(row0, row1, bloco):
                alt = min(bloco, row1 - r)
                alt -= alt % FATOR
                if alt <= 0:
                    continue
                larg = col1 - col0
                larg -= larg % FATOR
                if larg <= 0:
                    continue

                dados = src.read(1, window=Window(col0, r, larg, alt))
                # (alt/F, F, larg/F, F) -> conta cada classe por celula
                vista = dados.reshape(alt // FATOR, FATOR, larg // FATOR, FATOR)

                lon0 = t.c + col0 * t.a
                lat0 = t.f + r * t.e
                gi = int(round((RS_BBOX["lat_max"] - lat0) / RES_SAIDA))
                gj = int(round((lon0 - RS_BBOX["lon_min"]) / RES_SAIDA))

                for cat, classes in CATEGORIAS.items():
                    mask = np.isin(vista, classes)
                    bloco_counts = mask.sum(axis=(1, 3)).astype(np.int32)
                    h, w = bloco_counts.shape
                    # Recorta o que cai fora da grade (tiles ultrapassam o bbox)
                    i0, j0 = max(gi, 0), max(gj, 0)
                    i1, j1 = min(gi + h, n_lat), min(gj + w, n_lon)
                    if i1 <= i0 or j1 <= j0:
                        continue
                    counts[cat][i0:i1, j0:j1] += bloco_counts[i0 - gi:i1 - gi, j0 - gj:j1 - gj]

    return Grade(counts=counts, lon_min=RS_BBOX["lon_min"], lat_max=RS_BBOX["lat_max"],
                 n_lon=n_lon, n_lat=n_lat)


def area_pixel_km2(lat: float) -> float:
    """Area de um pixel nativo do JRC na latitude dada, em km².

    Sem projecao de area igual: a 30° de latitude o erro do cosseno simples
    contra uma projecao equivalente e da ordem de 0,1% — irrelevante diante da
    incerteza do proprio classificador de 30 m, e evita arrastar pyproj para
    dentro do projeto por causa da terceira casa decimal.
    """
    m_lon = RES_NATIVA * 111_320.0 * np.cos(np.radians(lat))
    m_lat = RES_NATIVA * 110_540.0
    return float(m_lon * m_lat) / 1e6


def salvar(grade: Grade) -> dict:
    """Grava a grade agregada e o resumo estadual."""
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)

    lats = grade.lat_max - (np.arange(grade.n_lat) + 0.5) * RES_SAIDA
    area_linha = np.array([area_pixel_km2(la) for la in lats])[:, None]

    resumo = {}
    areas = {}
    for cat, arr in grade.counts.items():
        km2 = float((arr * area_linha).sum())
        areas[cat] = arr
        resumo[cat] = round(km2, 1)

    np.savez_compressed(
        DATA_INTERIM / f"{SOURCE_ID}_rs_grade.npz",
        **{f"count_{k}": v for k, v in areas.items()},
        meta=np.array([json.dumps({
            "bbox": grade.bbox,
            "res_saida": RES_SAIDA,
            "res_nativa": RES_NATIVA,
            "fator": FATOR,
            "n_lon": grade.n_lon,
            "n_lat": grade.n_lat,
        })], dtype=object),
    )

    resumo_completo = {
        "produto": "JRC Global Surface Water v1.4",
        "janela": "1984-2021",
        "nao_cobre": "cheia de maio de 2024 — a serie termina em 2021",
        "resolucao_nativa_m": 30,
        "resolucao_grade_graus": RES_SAIDA,
        "area_km2": resumo,
        "referencia": "Pekel, J.-F. et al. High-resolution mapping of global surface water and its long-term changes. Nature 540, 418-422 (2016).",
    }
    (DATA_INTERIM / f"{SOURCE_ID}_rs_resumo.json").write_text(
        json.dumps(resumo_completo, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return resumo_completo


def run() -> dict:
    raw_dir = baixar_tiles()
    grade = agregar(raw_dir)
    return salvar(grade)


if __name__ == "__main__":
    r = run()
    print(f"[OK] {SOURCE_ID} — {r['janela']}")
    for k, v in r["area_km2"].items():
        print(f"     {k:12s} {v:>10.1f} km²")
    sys.exit(0)
