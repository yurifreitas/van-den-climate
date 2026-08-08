"""Divisao hidrografica da ANA — o regime de cheia de cada municipio.

Por que esta camada importa mais do que parece
==============================================

Dois municipios com o mesmo indice de risco podem precisar de obras opostas, e
o que decide isso e o REGIME de cheia — nao a magnitude do risco.

No Rio Grande do Sul ha tres regimes, e a diferenca entre eles e fisica:

**lagunar**  Guaiba, Lagoa dos Patos, Mirim/Sao Goncalo e as lagoas costeiras.
             O nivel aqui NAO e governado pela chuva local: e governado por
             VENTO. Vento de sul e sudeste empilha agua no eixo da laguna e
             bloqueia a saida no canal de Rio Grande, represando tudo o que
             desce. A Lagoa dos Patos e microtidal (~0,5 m em Rio Grande, e
             fortemente amortecida para dentro) — mare astronomica nao e o
             mecanismo, mare METEOROLOGICA e.

             Consequencia pratica: drenagem por gravidade FALHA quando a
             laguna sobe, porque nao ha para onde drenar. Dique e comporta
             funcionam; bueiro nao. E previsao util depende de vento, nao so
             de chuva.

**fluvial com remanso**  Taquari/Antas, Cai, Sinos, Gravatai, Baixo Jacui,
             Camaqua. A cheia PROPRIA e fluvial — rapida, deflagrada por chuva
             a montante, com pico em horas. Mas o trecho baixo sofre remanso
             quando o Guaiba esta alto: a agua desce e nao tem para onde ir.
             Sao os dois mecanismos somados, e foi o que aconteceu em 2024.

**fluvial**  Ibicui, Quarai, Santa Maria, Vacacai, Alto Jacui, Iju i, Passo
             Fundo, Turvo/Santa Rosa, Varzea, Apuae/Inhandava, Pelotas,
             Canoas, Butui/Icamaqua/Piratinim. Drenam para o rio Uruguai ou
             sao cabeceira. Vento nao entra. A cheia e funcao de chuva a
             montante e de tempo de concentracao da bacia.

O QUE ESTA CAMADA NAO E
=======================

Nao e modelo hidrodinamico. Nao calcula nivel, nao propaga onda de cheia, nao
tem batimetria nem condicao de contorno. Classifica MECANISMO, que e uma
afirmacao qualitativa e verificavel — e que muda a escolha de obra.

Um modelo hidrodinamico do sistema Guaiba-Patos exigiria batimetria da laguna,
MDT de alta resolucao da planicie, series de vazao dos cinco formadores, campo
de vento no eixo lagunar e nivel oceanico em Rio Grande, todos calibrados
contra eventos observados. Nenhum desses esta disponivel em fonte publica
utilizavel — testado: a telemetria da ANA devolveu erro e a API de dados do
INMET responde 204 em todo pedido.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"
MALHA_GEOJSON = DATA_INTERIM / "ibge_malha_rs.geojson"

SOURCE_ID = "ana_bacias"
INGESTOR_VERSION = "1"
URL = "https://www.snirh.gov.br/arcgis/rest/services/Divisoes_bacias_hidrograficas/MapServer/2/query"
CACHE_HORAS = 24 * 90  # divisao hidrografica muda por revisao institucional

# Regime por microbacia. E uma CLASSIFICACAO EDITORIAL fundamentada em
# hidrologia documentada, nao um campo do dado da ANA — a ANA fornece o
# poligono e o nome, a leitura do mecanismo e nossa e esta escrita aqui para
# que discordar seja facil e localizado.
REGIME: dict[str, str] = {
    # Nivel governado por vento; drenagem por gravidade falha quando sobe.
    "Guaíba": "lagunar",
    "Patos": "lagunar",
    "Mirim/São Gonçalo": "lagunar",
    "Tramandaí": "lagunar",
    # Cheia fluvial propria + remanso da laguna no trecho baixo.
    "Baixo Jacuí": "fluvial_com_remanso",
    "Taquari/Antas": "fluvial_com_remanso",
    "Caí": "fluvial_com_remanso",
    "Sinos": "fluvial_com_remanso",
    "Gravataí": "fluvial_com_remanso",
    "Camaquã": "fluvial_com_remanso",
    # Drenam para o Uruguai ou sao cabeceira: vento nao entra.
    "Alto Jacuí": "fluvial",
    "Ibicuí": "fluvial",
    "Quaraí": "fluvial",
    "Santa Maria": "fluvial",
    "Vacacaí": "fluvial",
    "Pardo (RS)": "fluvial",
    "Negro (RS)": "fluvial",
    "Ijuí": "fluvial",
    "Passo Fundo": "fluvial",
    "Turvo/Santa Rosa/Comandaí": "fluvial",
    "Várzea": "fluvial",
    "Apuaê/Inhandava": "fluvial",
    "Butuí/Icamaquã/Piratinim": "fluvial",
    "Pelotas": "fluvial",
    "Canoas": "fluvial",
    "Mampituba": "fluvial",
    "Peperi-Guaçu/Antas": "fluvial",
}

# Excecoes por centroide, nomeadas uma a uma em vez de resolvidas por default.
# Um fallback generico ("sem bacia -> fluvial") acertaria por acaso num caso e
# erraria feio no outro, e ninguem saberia qual foi qual.
OVERRIDE_MUNICIPIO: dict[int, tuple[str, str]] = {
    # Peninsula estreita entre a Lagoa dos Patos e o Atlantico. O centroide cai
    # sobre agua, que nao pertence a poligono de bacia nenhum — mas o municipio
    # e literalmente margem da laguna, e o regime e lagunar sem ambiguidade.
    4318507: ("Patos", "lagunar"),  # Sao Jose do Norte
    # Na divisa RS/SC sobre o rio Uruguai. O centroide cai na bacia do Peixe,
    # catalogada como catarinense; o regime, porem, e o do Uruguai: fluvial,
    # sem qualquer influencia de vento lagunar.
    4311908: ("Peixe (SC)", "fluvial"),  # Marcelino Ramos
}

ROTULO_REGIME = {
    "lagunar": "Lagunar — nivel governado por vento",
    "fluvial_com_remanso": "Fluvial com remanso da laguna",
    "fluvial": "Fluvial — sem influencia de vento",
}


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


def _get(params: dict[str, str], tentativas: int = 3) -> bytes:
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    url = f"{URL}?{urllib.parse.urlencode(params)}"
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            ultimo = exc
            if i < tentativas - 1:
                time.sleep(3 * (i + 1))
    raise IngestError(f"{SOURCE_ID}: falha na etapa fetch: {ultimo}")


def _latest_raw_dir() -> Path | None:
    base = DATA_RAW / SOURCE_ID
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


PARAMS = {
    "geometry": "-58,-34,-49,-27",
    "geometryType": "esriGeometryEnvelope",
    "inSR": "4326",
    "spatialRel": "esriSpatialRelIntersects",
    "outFields": "DMI_CD,DMI_NM,DMI_AR_KM2",
    "returnGeometry": "true",
    "outSR": "4326",
    "f": "geojson",
}


def _aneis(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [anel for poly in geometry["coordinates"] for anel in poly]


def _ponto_em_anel(lon: float, lat: float, anel: list) -> bool:
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
    return dentro


def run() -> pd.DataFrame:
    latest = _latest_raw_dir()
    usar_cache = False
    if latest is not None and (latest / "payload.geojson").exists():
        prov = json.loads((latest / "provenance.json").read_text(encoding="utf-8"))
        idade = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(prov["fetched_at"])).total_seconds() / 3600
        usar_cache = idade <= CACHE_HORAS or os.environ.get("CLIMATE_OFFLINE") == "1"

    if usar_cache and latest is not None:
        raw = (latest / "payload.geojson").read_bytes()
        raw_dir = latest
    else:
        raw = _get(PARAMS)
        raw_dir = DATA_RAW / SOURCE_ID / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / "payload.geojson").write_bytes(raw)
        (raw_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "url": URL,
                    "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "product_version": "ANA/SNIRH — Micro Regiao Hidrografica",
                    "ingestor_version": INGESTOR_VERSION,
                    "rows": None,
                    "notes": (
                        "Microbacias que intersectam a caixa do RS. O REGIME (lagunar / "
                        "fluvial com remanso / fluvial) e classificacao editorial deste "
                        "projeto sobre o poligono da ANA, nao campo do dado original."
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    geo = json.loads(raw.decode("utf-8"))
    feats = geo.get("features", [])
    if not feats:
        raise IngestError(f"{SOURCE_ID}: nenhuma microbacia retornada")

    # Atribui regime ao municipio pelo centroide: a microbacia que contem o
    # centroide define o regime dominante. Municipio a cavaleiro de duas bacias
    # existe e fica com a do centroide — aproximacao declarada, e a alternativa
    # (fracao de area por bacia) nao mudaria a escolha de obra.
    if not MALHA_GEOJSON.exists():
        raise IngestError(
            f"{SOURCE_ID}: malha ausente — rode `python -m src.ingest.ibge_rs malha`"
        )
    malha = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))

    bacias = []
    for f in feats:
        nome = f["properties"].get("DMI_NM")
        bacias.append({
            "nome": nome,
            "codigo": f["properties"].get("DMI_CD"),
            "area_km2": f["properties"].get("DMI_AR_KM2"),
            "regime": REGIME.get(nome),
            "aneis": _aneis(f["geometry"]),
        })

    linhas = []
    for f in malha["features"]:
        cod = int(f["properties"]["codarea"])
        pts = [p for anel in _aneis(f["geometry"]) for p in anel]
        clon = sum(p[0] for p in pts) / len(pts)
        clat = sum(p[1] for p in pts) / len(pts)
        achou = None
        for b in bacias:
            if any(_ponto_em_anel(clon, clat, a) for a in b["aneis"]):
                achou = b
                break
        bacia = achou["nome"] if achou else None
        regime = (achou or {}).get("regime")
        if cod in OVERRIDE_MUNICIPIO:
            bacia_ov, regime_ov = OVERRIDE_MUNICIPIO[cod]
            bacia = bacia or bacia_ov
            regime = regime_ov
        linhas.append({
            "cod_mun": cod,
            "bacia": bacia,
            "bacia_codigo": achou["codigo"] if achou else None,
            "regime": regime,
        })

    df = pd.DataFrame(linhas)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_INTERIM / f"{SOURCE_ID}.parquet", index=False)

    prov_path = raw_dir / "provenance.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        prov["rows"] = len(df)
        prov_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    return df


if __name__ == "__main__":
    d = run()
    print(f"[OK] {SOURCE_ID}: {len(d)} municipios classificados")
    print(d["regime"].value_counts(dropna=False).to_string())
    sem = d[d["bacia"].isna()]
    if len(sem):
        print(f"     sem bacia atribuida: {len(sem)}")
    sys.exit(0)
