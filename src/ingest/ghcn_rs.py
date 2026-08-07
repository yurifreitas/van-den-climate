"""GHCN-Daily — a serie mais longa de chuva que existe para o RS.

Por que esta fonte muda o projeto
=================================

Ate aqui a engine tinha teleconexao (ONI desde 1950) e impacto de UM evento
(MUNIC 2024). Faltava o meio: a resposta observada do territorio a chuva, ano
a ano, por decadas. Sem isso, o alvo declarado na ADR-002 — o trio (frequencia
de dias umidos, intensidade em dia umido, p95 diario) — nunca teve dado real.

O Global Historical Climatology Network Daily traz 224 estacoes dentro da
caixa do RS, 53 delas com 40 anos ou mais de precipitacao diaria, a mais longa
comecando em 1929. Com ONI de 1950 em diante e chuva diaria desde os anos 30,
da para medir — com dado, nao com literatura — quanto El Nino de fato deslocou
a chuva de primavera no RS.

O LIMITE QUE DEFINE ESTA CAMADA
===============================

**As series brasileiras do GHCN-Daily terminam entre 1997 e 1999.** O NCEI
parou de receber atualizacao do Brasil. Isto NAO e uma serie operacional e
nao serve para monitorar a estacao corrente: e um arquivo historico.

A consequencia e boa e precisa ser dita: a camada historica e cega ao evento
de 2024, como o JRC e cego a ele. Toda concordancia entre o que a historia diz
e o que 2024 mostrou e, de novo, encontro de bases independentes — nao
circularidade.

Outros limites, todos declarados no payload:
  - Sem homogeneizacao. A Camada 2 do projeto (quebras, mudanca de sitio,
    troca de instrumento) nao foi construida. Series longas de estacao tem
    descontinuidade quase por definicao.
  - Cobertura desigual: estacao com 55 anos pode ter meses inteiros vazios.
  - A caixa geografica do RS pega Santa Catarina. O recorte aqui e por
    POLIGONO municipal do IBGE, nao por caixa — ver `_dentro_do_rs`.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"
MALHA_GEOJSON = DATA_INTERIM / "ibge_malha_rs.geojson"

SOURCE_ID = "ghcn_rs"
INGESTOR_VERSION = "1"
BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily"

# Minimo de anos de PRCP para a estacao entrar. 30 e o piso classico de
# climatologia; abaixo disso a distribuicao de extremos nao tem forma.
MIN_ANOS = 30

# Caixa so para pre-filtrar o inventario de 125 mil estacoes. O recorte de
# verdade e por poligono, logo abaixo.
CAIXA = {"lat_min": -34.0, "lat_max": -26.8, "lon_min": -58.0, "lon_max": -49.3}


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


def _get(url: str, tentativas: int = 3) -> bytes:
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            ultimo = exc
            if i < tentativas - 1:
                time.sleep(2**i)
    raise IngestError(f"{SOURCE_ID}: falha na etapa fetch, url={url}: {ultimo}")


# ---------------------------------------------------------------------------
# Recorte por poligono
# ---------------------------------------------------------------------------
def _aneis(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [anel for poly in geometry["coordinates"] for anel in poly]


def _ponto_em_anel(lon: float, lat: float, anel: list[list[float]]) -> bool:
    """Ray casting. Exato e sem dependencia — 497 poligonos nao pedem indice espacial."""
    dentro = False
    n = len(anel)
    j = n - 1
    for i in range(n):
        xi, yi = anel[i][0], anel[i][1]
        xj, yj = anel[j][0], anel[j][1]
        if (yi > lat) != (yj > lat):
            corte = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < corte:
                dentro = not dentro
        j = i
    return dentro


def _municipios() -> list[tuple[int, list[list[list[float]]], tuple[float, float, float, float]]]:
    if not MALHA_GEOJSON.exists():
        raise IngestError(
            f"{SOURCE_ID}: malha ausente ({MALHA_GEOJSON}) — rode `python -m src.ingest.ibge_rs malha`. "
            "Sem ela o recorte cai para caixa, e a caixa do RS pega Santa Catarina."
        )
    geo = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    out = []
    for f in geo["features"]:
        aneis = _aneis(f["geometry"])
        pts = [p for a in aneis for p in a]
        bb = (
            min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts),
        )
        out.append((int(f["properties"]["codarea"]), aneis, bb))
    return out


def _dentro_do_rs(lon: float, lat: float, mun) -> int | None:
    """Codigo do municipio que contem o ponto, ou None se fora do estado."""
    for cod, aneis, (x0, y0, x1, y1) in mun:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue  # bbox barato antes do ray casting
        if any(_ponto_em_anel(lon, lat, a) for a in aneis):
            return cod
    return None


# ---------------------------------------------------------------------------
# Selecao de estacoes
# ---------------------------------------------------------------------------
def selecionar() -> pd.DataFrame:
    print("  inventario de estacoes...", flush=True)
    stations = _get(f"{BASE}/ghcnd-stations.txt").decode("utf-8", errors="replace")
    print("  inventario de elementos...", flush=True)
    inv = _get(f"{BASE}/ghcnd-inventory.txt").decode("utf-8", errors="replace")

    candidatas: dict[str, dict] = {}
    for ln in stations.splitlines():
        if not ln.startswith("BR"):
            continue
        lat, lon = float(ln[12:20]), float(ln[21:30])
        if not (CAIXA["lat_min"] <= lat <= CAIXA["lat_max"] and CAIXA["lon_min"] <= lon <= CAIXA["lon_max"]):
            continue
        candidatas[ln[0:11]] = {"station_id": ln[0:11], "nome": ln[41:71].strip(), "lat": lat, "lon": lon}

    for ln in inv.splitlines():
        sid = ln[0:11]
        if sid not in candidatas or ln[31:35].strip() != "PRCP":
            continue
        candidatas[sid].update({"prcp_ini": int(ln[36:40]), "prcp_fim": int(ln[41:45])})

    df = pd.DataFrame([c for c in candidatas.values() if "prcp_ini" in c])
    if df.empty:
        raise IngestError(f"{SOURCE_ID}: nenhuma estacao com PRCP na caixa do RS")
    df["anos"] = df["prcp_fim"] - df["prcp_ini"] + 1
    df = df[df["anos"] >= MIN_ANOS].copy()

    mun = _municipios()
    df["cod_mun"] = [
        _dentro_do_rs(float(r.lon), float(r.lat), mun) for r in df.itertuples()
    ]
    fora = int(df["cod_mun"].isna().sum())
    df = df[df["cod_mun"].notna()].copy()
    df["cod_mun"] = df["cod_mun"].astype(int)
    print(f"  {len(df)} estacoes dentro do RS ({fora} descartadas por caírem fora do poligono)", flush=True)
    return df.sort_values("anos", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Parse do formato .dly (largura fixa)
# ---------------------------------------------------------------------------
def parse_dly(texto: str, station_id: str) -> pd.DataFrame:
    """.dly -> (station_id, data, prcp_mm).

    PRCP vem em DECIMOS de milimetro e -9999 e ausente. Esquecer a divisao por
    10 produz uma serie dez vezes maior que a realidade — plausivel o bastante
    para passar despercebida num grafico e catastrofica num percentil.
    """
    datas: list[pd.Timestamp] = []
    valores: list[float] = []
    for ln in texto.splitlines():
        if len(ln) < 269 or ln[17:21] != "PRCP":
            continue
        ano, mes = int(ln[11:15]), int(ln[15:17])
        for d in range(31):
            off = 21 + d * 8
            bruto = ln[off:off + 5].strip()
            if not bruto or bruto == "-9999":
                continue
            qflag = ln[off + 6:off + 7].strip()
            if qflag:  # qualquer flag de qualidade do proprio GHCN -> descarta
                continue
            try:
                data = pd.Timestamp(year=ano, month=mes, day=d + 1)
            except ValueError:
                continue  # dia 31 de mes de 30
            datas.append(data)
            valores.append(int(bruto) / 10.0)
    return pd.DataFrame({"station_id": station_id, "data": datas, "prcp_mm": valores})


def _latest_raw_dir() -> Path | None:
    base = DATA_RAW / SOURCE_ID
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def run() -> tuple[pd.DataFrame, pd.DataFrame]:
    latest = _latest_raw_dir()
    offline = os.environ.get("CLIMATE_OFFLINE") == "1"

    if latest is not None and (latest / "estacoes.csv").exists() and (offline or True):
        # Cache agressivo: o arquivo historico nao muda (as series terminam em
        # 1999). Rebaixar 6 MB a cada execucao seria desperdicio puro.
        estacoes = pd.read_csv(latest / "estacoes.csv")
        raw_dir = latest
        print(f"  usando cache de {raw_dir.name}", flush=True)
    else:
        if offline:
            raise IngestError(f"{SOURCE_ID}: modo offline sem download previo")
        estacoes = selecionar()
        raw_dir = DATA_RAW / SOURCE_ID / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
        (raw_dir / "dly").mkdir(parents=True, exist_ok=True)
        estacoes.to_csv(raw_dir / "estacoes.csv", index=False)
        for i, sid in enumerate(estacoes["station_id"], 1):
            dest = raw_dir / "dly" / f"{sid}.dly"
            if dest.exists():
                continue
            dest.write_bytes(_get(f"{BASE}/all/{sid}.dly"))
            if i % 10 == 0:
                print(f"    {i}/{len(estacoes)}", flush=True)

    quadros = []
    for sid in estacoes["station_id"]:
        caminho = raw_dir / "dly" / f"{sid}.dly"
        if not caminho.exists():
            continue
        quadros.append(parse_dly(caminho.read_text(encoding="utf-8", errors="replace"), sid))
    diario = pd.concat(quadros, ignore_index=True) if quadros else pd.DataFrame()
    if diario.empty:
        raise IngestError(f"{SOURCE_ID}: nenhum registro diario parseado")

    if not (raw_dir / "provenance.json").exists():
        conteudo = b"".join(sorted(p.read_bytes() for p in (raw_dir / "dly").glob("*.dly")))
        (raw_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "url": BASE,
                    "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
                    "sha256": hashlib.sha256(conteudo).hexdigest(),
                    "product_version": "GHCN-Daily",
                    "ingestor_version": INGESTOR_VERSION,
                    "rows": int(len(diario)),
                    "notes": (
                        f"{len(estacoes)} estacoes dentro do poligono do RS, PRCP >= {MIN_ANOS} anos. "
                        "As series brasileiras do GHCN-Daily terminam entre 1997 e 1999 — "
                        "arquivo historico, NAO serie operacional."
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    diario.to_parquet(DATA_INTERIM / f"{SOURCE_ID}_diario.parquet", index=False)
    estacoes.to_parquet(DATA_INTERIM / f"{SOURCE_ID}_estacoes.parquet", index=False)
    return estacoes, diario


if __name__ == "__main__":
    est, dia = run()
    anos = dia["data"].dt.year
    print(f"[OK] {SOURCE_ID}: {len(est)} estacoes, {len(dia):,} dias de chuva")
    print(f"     periodo {int(anos.min())}–{int(anos.max())}")
    print(f"     media de {len(dia) / len(est) / 365.25:.0f} anos-estacao por estacao")
    sys.exit(0)
