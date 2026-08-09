"""NOAA CPC — a chuva que caiu ate ontem, sobre o estado inteiro.

O BURACO QUE ESTA FONTE FECHA
=============================

A central tinha chuva HISTORICA (GHCN, 66 estacoes, 1934-2022) e tinha o
estado do oceano ATUAL (ONI, SOI, AAO, mensais). Nao tinha a unica coisa que
uma central de risco precisa saber para falar do proximo fim de semana:
**quanto choveu na semana passada**.

Isso nao e detalhe operacional. O modelo de escoamento em `src/risk/hidrologia.py`
publica dois numeros para cada municipio — o Curve Number de solo seco e o de
solo encharcado — porque a mesma chuva escoa quase o dobro quando o perfil ja
esta cheio. Qual dos dois vale HOJE nao era pergunta que a central pudesse
responder: faltava a chuva antecedente. Com esta fonte, passa a ser medida.

O PRODUTO
=========

CPC Global Unified Gauge-Based Analysis of Daily Precipitation, do Climate
Prediction Center (NOAA). Grade global de 0,5 grau, diaria, de 1979 ate
ontem, construida por interpolacao otimizada de **pluviometros** — nao e
satelite, nao e modelo, nao e reanalise. Onde ha rede densa, e a melhor
estimativa em grade disponivel; onde a rede e rala, a interpolacao inventa
suavidade que nao existe.

A CELULA TEM 55 km, E ISSO MUDA A LEITURA
=========================================

Meio grau no RS e cerca de 55 km — maior que a maioria dos municipios do
estado. Consequencias que precisam viajar em todo numero daqui:

  1. Municipios vizinhos COMPARTILHAM celula. Nao ha diferenca de chuva entre
     eles neste dado, e qualquer ranking municipal baseado so nisto e ranking
     de celula com nome de municipio. O payload declara quantos municipios
     dividem cada celula.

  2. A celula e uma MEDIA de area. Uma tempestade convectiva de 15 km que
     despeja 120 mm aparece aqui como 20 mm espalhados — e no RS de verao a
     chuva que causa alagamento urbano e exatamente essa. O dado subestima
     sistematicamente o extremo pontual, e por isso NAO substitui a estacao.

  3. Isto e chuva OBSERVADA, nunca prevista. A central nao emite previsao de
     chuva (ADR-013), e esta fonte nao muda isso: ela olha para tras.

POR QUE NAO INMET
=================

O INMET seria a fonte natural — 98 estacoes automaticas so no RS, horarias.
Mas a API publica devolve a lista de estacoes e responde `204 No Content` para
qualquer consulta de DADOS, em qualquer data testada, com ou sem token. O
caminho oficial restante e o BDMEP, que exige login. Enquanto isso nao se
resolver, o CPC e o que ha de aberto, atual e cobrindo o estado todo — com a
celula de 55 km declarada em cada leitura.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

SOURCE_ID = "cpc_precip"
INGESTOR_VERSION = "1"
BASE_URL = "https://downloads.psl.noaa.gov/Datasets/cpc_global_precip"
SAIDA = DATA_INTERIM / "cpc_precip_rs.parquet"
META_SAIDA = DATA_INTERIM / "cpc_precip_rs.meta.json"

MALHA_GEOJSON = DATA_INTERIM / "ibge_malha_rs.geojson"
MUNIC_PARQUET = DATA_INTERIM / "ibge_munic_rs.parquet"

# Janela guardada. 400 dias cobre o ano corrente inteiro mais a virada, que e
# o que as janelas antecedentes (5, 30, 90 dias) precisam em qualquer data.
DIAS_GUARDADOS = 400

# O arquivo do ano corrente e reescrito pelo CPC todo dia. Cache curto: um
# payload de ontem serve para desenvolver, nao para publicar.
CACHE_HORAS = 12

BBOX = {"lon_min": -58.2, "lon_max": -49.1, "lat_min": -34.3, "lat_max": -26.5}


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


@dataclass(frozen=True)
class Resultado:
    df: pd.DataFrame
    meta: dict[str, Any]


def _baixar(ano: int, destino: Path) -> Path:
    url = f"{BASE_URL}/precip.{ano}.nc"
    arq = destino / f"precip.{ano}.nc"
    if arq.exists():
        return arq
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
        with urllib.request.urlopen(req, timeout=900) as r:
            dados = r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise IngestError(f"{SOURCE_ID}: falha na etapa fetch de {url}: {exc}") from exc
    destino.mkdir(parents=True, exist_ok=True)
    arq.write_bytes(dados)
    (destino / f"provenance.precip.{ano}.json").write_text(
        json.dumps(
            {
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(dados).hexdigest(),
                "product_version": "CPC Global Unified Gauge-Based Daily Precipitation (0.5 deg)",
                "ingestor_version": INGESTOR_VERSION,
                "bytes": len(dados),
                "notes": (
                    "Interpolacao de PLUVIOMETROS, nao satelite nem modelo. Celula de "
                    "~55 km: subestima sistematicamente a tempestade convectiva pontual."
                ),
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return arq


def _raw_dir_recente() -> Path | None:
    base = DATA_RAW / SOURCE_ID
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    if not dirs:
        return None
    prov = sorted(dirs[0].glob("provenance.*.json"))
    if not prov:
        return None
    quando = json.loads(prov[-1].read_text(encoding="utf-8"))["fetched_at"]
    idade_h = (datetime.now(timezone.utc) - datetime.fromisoformat(quando)).total_seconds() / 3600
    if idade_h <= CACHE_HORAS or os.environ.get("CLIMATE_OFFLINE") == "1":
        return dirs[0]
    return None


def _ler_ano(arq: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[date]]:
    """(cubo[t,lat,lon], lats, lons, datas) recortado na caixa do RS.

    O arquivo e NetCDF-4, que o `scipy.io.netcdf_file` nao le — e nao ha
    netCDF4 nem xarray no ambiente. O GDAL que vem com o rasterio le, e o
    subdataset `netcdf:<arquivo>:precip` expoe cada dia como uma banda. Usar o
    que ja esta instalado evita uma dependencia pesada por uma leitura so.
    """
    import rasterio

    with rasterio.open(f"netcdf:{arq.as_posix()}:precip") as src:
        tags = src.tags()
        n_lat, n_lon = src.shape
        # A grade do CPC tem longitude 0..360 e latitude do sul para o norte;
        # o GDAL entrega a matriz ja com a origem no topo. Reconstruir os
        # eixos a partir do transform e mais seguro que assumir a convencao.
        t = src.transform
        lons = np.array([t.c + (i + 0.5) * t.a for i in range(n_lon)])
        lats = np.array([t.f + (j + 0.5) * t.e for j in range(n_lat)])
        # 0..360 -> -180..180 para casar com a caixa do RS.
        lons180 = np.where(lons > 180, lons - 360, lons)

        col = np.where((lons180 >= BBOX["lon_min"] - 0.5) & (lons180 <= BBOX["lon_max"] + 0.5))[0]
        lin = np.where((lats >= BBOX["lat_min"] - 0.5) & (lats <= BBOX["lat_max"] + 0.5))[0]
        if col.size == 0 or lin.size == 0:
            raise IngestError(f"{SOURCE_ID}: recorte do RS vazio — a grade do produto mudou")

        janela = rasterio.windows.Window(
            int(col.min()), int(lin.min()), int(col.size), int(lin.size)
        )
        cubo = src.read(window=janela).astype("float32")
        nodata = src.nodatavals[0] if src.nodatavals else None
        if nodata is not None:
            cubo[cubo == nodata] = np.nan
        cubo[cubo < 0] = np.nan

        origem = tags.get("time#units", "")
        datas = _datas(origem, src.count, tags)
    return cubo, lats[lin], lons180[col], datas


def _datas(units: str, n: int, tags: dict) -> list[date]:
    """Datas das bandas, a partir de `time#units` e dos valores de tempo.

    A UNIDADE PRECISA SER LIDA, NUNCA ASSUMIDA. O produto declara
    "hours since 1900-01-01", e tratar isso como dias — o palpite natural para
    uma serie diaria — devolve datas no ano 4912 sem erro nenhum: a serie sai
    completa, ordenada e coerente, so que tres mil anos no futuro. Foi
    exatamente o que aconteceu na primeira execucao, e so apareceu porque a
    saida imprime o primeiro e o ultimo dia.

    Ler a origem do arquivo tambem evita o erro classico de virada de ano, em
    que o arquivo novo tem poucos dias e um indice presumido a partir de 1 de
    janeiro desloca a serie inteira.
    """
    base, escala = None, None
    if "since" in units:
        unidade, _, resto = units.partition("since")
        escala = {"day": 1.0, "days": 1.0, "hour": 1 / 24, "hours": 1 / 24,
                  "minute": 1 / 1440, "minutes": 1 / 1440}.get(unidade.strip().lower())
        try:
            base = datetime.fromisoformat(resto.strip().split()[0]).date()
        except ValueError:
            base = None
    valores = tags.get("NETCDF_DIM_time_VALUES")
    if base is not None and escala is not None and valores:
        nums = [float(x) for x in valores.strip("{}").split(",")]
        return [base + timedelta(days=round(v * escala)) for v in nums[:n]]
    raise IngestError(
        f"{SOURCE_ID}: nao foi possivel ler o eixo de tempo (units={units!r}) — "
        "sem data confiavel a serie inteira pode sair deslocada, e sair errada "
        "em silencio e pior que nao sair."
    )


def _centroides() -> dict[int, tuple[float, float]]:
    geo = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    saida: dict[int, tuple[float, float]] = {}
    for f in geo["features"]:
        g = f["geometry"]
        aneis = g["coordinates"] if g["type"] == "Polygon" else [
            anel for poly in g["coordinates"] for anel in poly
        ]
        pts = [p for anel in aneis for p in anel]
        saida[int(f["properties"]["codarea"])] = (
            float(np.mean([p[0] for p in pts])),
            float(np.mean([p[1] for p in pts])),
        )
    return saida


def build() -> Resultado:
    if not MALHA_GEOJSON.exists():
        raise FileNotFoundError(f"{MALHA_GEOJSON} ausente — rode `python -m src.ingest.ibge_rs`")

    cache = _raw_dir_recente()
    destino = cache or (DATA_RAW / SOURCE_ID / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S"))

    hoje = date.today()
    anos = sorted({hoje.year, (hoje - timedelta(days=DIAS_GUARDADOS)).year})
    cubos, latss, lonss, todas_datas = [], None, None, []
    for ano in anos:
        try:
            arq = _baixar(ano, destino)
        except IngestError:
            if ano == anos[-1]:
                raise
            continue    # ano anterior indisponivel nao impede o ano corrente
        cubo, lats, lons, datas = _ler_ano(arq)
        cubos.append(cubo)
        todas_datas.extend(datas)
        latss, lonss = lats, lons

    if not cubos:
        raise IngestError(f"{SOURCE_ID}: nenhum ano baixado")
    cubo = np.concatenate(cubos, axis=0)

    # Dia sem dado no fim do arquivo: o CPC preenche o ano inteiro e so
    # escreve os dias ja processados. Cortar aqui evita publicar uma fila de
    # zeros como se fosse seca.
    validos = ~np.all(np.isnan(cubo.reshape(len(cubo), -1)), axis=1)
    cubo, todas_datas = cubo[validos], [d for d, v in zip(todas_datas, validos) if v]
    if not todas_datas:
        raise IngestError(f"{SOURCE_ID}: arquivo sem nenhum dia valido")

    corte = max(0, len(todas_datas) - DIAS_GUARDADOS)
    cubo, todas_datas = cubo[corte:], todas_datas[corte:]

    centroides = _centroides()
    munic = pd.read_parquet(MUNIC_PARQUET)[["cod_mun", "municipio"]]
    nomes = {int(r.cod_mun): r.municipio for r in munic.itertuples()}

    linhas = []
    celulas: dict[tuple[int, int], list[int]] = {}
    for cod, (lon, lat) in centroides.items():
        j = int(np.argmin(np.abs(lonss - lon)))
        i = int(np.argmin(np.abs(latss - lat)))
        celulas.setdefault((i, j), []).append(cod)
        serie = cubo[:, i, j]
        for d, v in zip(todas_datas, serie):
            if np.isnan(v):
                continue
            linhas.append({
                "cod_mun": cod,
                "municipio": nomes.get(cod),
                "data": d,
                "prcp_mm": round(float(v), 2),
                "celula_lat": round(float(latss[i]), 2),
                "celula_lon": round(float(lonss[j]), 2),
            })

    df = pd.DataFrame(linhas).sort_values(["cod_mun", "data"]).reset_index(drop=True)
    compartilhando = [len(v) for v in celulas.values()]

    meta = {
        "version": INGESTOR_VERSION,
        "fonte": (
            "NOAA CPC Global Unified Gauge-Based Analysis of Daily Precipitation "
            "(0,5 grau), via NOAA PSL. Interpolacao de pluviometros."
        ),
        "primeiro_dia": str(min(todas_datas)),
        "ultimo_dia": str(max(todas_datas)),
        "n_dias": len(todas_datas),
        "n_municipios": int(df.cod_mun.nunique()),
        "n_celulas": len(celulas),
        "municipios_por_celula_max": int(max(compartilhando)),
        "municipios_por_celula_mediana": float(np.median(compartilhando)),
        "limites": [
            "Celula de 0,5 grau (~55 km) e maior que a maioria dos municipios do RS: "
            f"ate {max(compartilhando)} municipios dividem a MESMA celula e nao tem "
            "diferenca de chuva neste dado.",
            "A celula e media de area. Tempestade convectiva de 15 km com 120 mm "
            "aparece como ~20 mm espalhados — o produto subestima o extremo pontual "
            "por construcao, e nao substitui estacao.",
            "E chuva OBSERVADA, nunca prevista. A central nao emite previsao de chuva.",
            "Interpolacao de pluviometros: onde a rede e rala, a suavidade do campo e "
            "do metodo, nao do tempo.",
        ],
    }
    return Resultado(df=df, meta=meta)


def main() -> int:
    r = build()
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    r.df.to_parquet(SAIDA, index=False)
    META_SAIDA.write_text(json.dumps(r.meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[OK] {SOURCE_ID}: {len(r.df)} linhas, {r.meta['n_dias']} dias "
          f"({r.meta['primeiro_dia']} a {r.meta['ultimo_dia']}) -> {SAIDA.name}")
    print(f"     {r.meta['n_celulas']} celulas cobrem 497 municipios; "
          f"ate {r.meta['municipios_por_celula_max']} municipios por celula")
    ultimo = r.df[r.df.data == r.df.data.max()]
    print(f"     chuva do ultimo dia: mediana {ultimo.prcp_mm.median():.1f} mm, "
          f"maxima {ultimo.prcp_mm.max():.1f} mm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
